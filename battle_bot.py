# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 thiliapr <thiliapr@tutanota.com>
# SPDX-Package: hentaiverse_battle_bot
# SPDX-PackageHomePage: https://github.com/thiliapr/hentaiverse_battle_bot

# 一开始这个脚本是用 Tampermonkey 用户脚本写的，后来才发现可以调 API，所以用 Python 写了
# 以前我专门写 Python，总觉得其他语言更好，Python 有各种问题
# 后来我写了一下 JavaScript（就是刚才说的那个，这个脚本的前身），终于领悟。JavaScript 都什么垃圾玩意，果然还是 Python 好用

import re
import pathlib
import argparse
import webbrowser
from typing import Any, Literal
import orjson
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

MAIN_URL = "https://hentaiverse.org"

# 配置和数据
class MagicInfo(BaseModel):
    name: str = Field(..., description="该魔法在游戏里的名称")
    mana_cost: int = Field(..., description="该魔法消耗的蓝量")
    attribute: Literal["fire", "cold", "elec", "wind", "holy", "dark"] = Field(..., description="魔法的攻击属性")


class BattleBotConfig(BaseModel):
    ipb_member_id: str = Field(..., description="从浏览器 Cookies 中获取对应名字的 cookie")
    ipb_pass_hash: str = Field(..., description="从浏览器 Cookies 中获取对应名字的 cookie")
    user_agent: str = Field(..., description="从浏览器中获取请求头 User-Agent 字段的值")
    attack_target_range: int = Field(..., description="魔法攻击的范围，请根据你的实际情况指定。0 代表只能攻击到指定的目标怪兽（共 1 个怪兽受到攻击），1 代表能够攻击目标怪兽以及上下各一个怪兽（共 3 个怪兽受到攻击），2 代表能够攻击目标怪兽以及上下各两个怪兽（共 5 个怪兽受到攻击），依此类推")
    # 你不知道敌人一拳打过来有多痛，万一一下就打死了呢？连回复的机会都没有
    safe_health_threshold: int = Field(..., description="安全的血量阈值，如果当前血量低于这个值，就回复血量")
    safe_mana_threshold: int = Field(..., description="安全的蓝量阈值，如果当前蓝量低于这个值，就回复蓝量")
    # 蓝量很少，攻击不够用怎么办？给耗蓝加权！
    mana_cost_weight: float = Field(1, description="耗蓝权重，值越大越优先使用低耗蓝魔法")
    # 战斗将要结束时，防御回蓝的目标，达到这个目标后将终结最后一个敌人
    end_battle_mana_target: float = Field(..., description="战斗结束前期望达到的蓝量，达到后终结最后一个敌人")
    # 不同等级的玩家，即使是同样的魔法，消耗的蓝量也不同。并且低等级还不能使用高等级的魔法
    attack_magic_skills: list[MagicInfo] = Field(..., description="所有当前可用的魔法")
    # 游戏有两个世界: / 和 /isekai。/ 代表 Persistent，玩家数据会一直保持；/isekai 是季度性的，每个季度会刷新，可以用于增幅 Persistent
    world: Literal["/", "/isekai"] = Field("/", description="游戏世界类型: /，代表 Persistent，永久保存角色进度；/isekai，代表 Isekai，季度重置，可获得增幅奖励")


class MonsterResistanceData(BaseModel):
    cold: int = Field(0, description="冰属性抗性（百分比）")
    wind: int = Field(0, description="风属性抗性（百分比）")
    elec: int = Field(0, description="电属性抗性（百分比）")
    fire: int = Field(0, description="火属性抗性（百分比）")
    holy: int = Field(0, description="圣属性抗性（百分比）")
    dark: int = Field(0, description="暗属性抗性（百分比）")


class EnemyData(BaseModel):
    # 其实 resistance 的创建完全可以用 default=MonsterResistanceData()，因为 Pydantic v2 已经支持 copy.deepcopy(default) 了
    # 不会存在共享了同一个实例问题。但是用 default 显得不够优雅，所以用 default_factory 了
    resistance: MonsterResistanceData = Field(default_factory=MonsterResistanceData, description="怪物的属性抗性数据，如果数据库中没有该怪物的数据，就假设它没有任何抗性")
    is_alive: bool = Field(True, description="怪物是否还活着")


# 正式程序
def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config-file", default=pathlib.Path("config.json"), type=pathlib.Path, help="配置文件路径")
    parser.add_argument("-d", "--database-file", default=pathlib.Path("monster_resistance_data.json"), type=pathlib.Path, help="怪物数据库文件路径")
    return parser.parse_args(args)


def request_with_retry(func, *args, retries: int = 3, **kwargs):
    while True:
        try:
            result = func(*args, **kwargs, timeout=30)
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"网络错误: {e}")
            retries -= 1
            if retries < 0:
                raise e
    return result


def try_to_get_item_id(item_name: str, soup_item: BeautifulSoup) -> str | None:
    item_string = soup_item.find(string=item_name)
    # 找不到物品，代表背包没这种物品，可能用光了
    if item_string is None:
        return
    item_container = item_string.parent.parent.parent
    # 如果药没有 onclick 事件，说明还在等 CD
    if "onclick" not in item_container.attrs:
        return
    # 因为 P 栏 Gem 类物品的 ID 是 ikey_p，但物品 ID 不是 P 而是 999
    # 为了处理这种情况，我们得从 onclick 事件提取 ID
    return re.search(r"battle.set_friendly_skill\('(\d+)'\)", item_container.attrs["onclick"]).group(1)


def try_to_get_magic_id(magic_name: str, soup_magic: BeautifulSoup) -> int | None:
    magic_string = soup_magic.find(string=magic_name)
    # 没找到魔法，大概是等级没达到，未解锁
    if magic_string is None:
        return
    magic_container = magic_string.parent.parent.parent
    # 如果魔法没有 onclick 事件，说明还在等 CD
    if "onclick" not in magic_container.attrs:
        return
    return int(magic_container.attrs["id"])


def get_player_health(soups: dict[str, BeautifulSoup]) -> int:
    # pane_vitals 显示一个血量条，血量条里面有一个 HP 标签，获取血量就是就是获取的这个标签的值
    # 但是这个血量条过短（对应着血量过低）时，这个 HP 标签就不会显示，对应的 DOM 对象就没有，那么我们就当作是 1 血吧
    if health_label := soups["pane_vitals"].find(id="vrhb"):
        return int(health_label.text)
    return 1


def get_player_mana(soups: dict[str, BeautifulSoup]) -> int:
    return int(soups["pane_vitals"].find(id="vrm").text)


def get_player_effects(soups: dict[str, BeautifulSoup]) -> set[str]:
    effects = set()
    for img in soups["pane_effects"].find_all("img"):
        effects.add(img.attrs["onmouseover"][len("battle.set_infopane_effect('"):].split("'", 1)[0])
    return effects


def update_enemy_data(enemy_list: list[EnemyData], soups: dict[str, BeautifulSoup]):
    # 更新敌人生死信息
    for i, enemy in enumerate(enemy_list, start=1):
        enemy.is_alive = "onclick" in soups["pane_monster"].find(id=f"mkey_{i}").attrs


def auto_battle(
    config: BattleBotConfig,
    database: dict[str, MonsterResistanceData],
    requests_kwargs: dict[str, Any]
) -> str | None:
    # 获取战斗界面和 battle_token
    # 震撼人心，这游戏居然没有复杂的 nonce 验证、CSRF 验证之类的安全措施。那还说啥，直接 API 跑起
    resp = request_with_retry(requests.get, f"{MAIN_URL}/{config.world}", **requests_kwargs)
    try:
        battle_token = re.search('var battle_token = "([^"]+)"', resp.text).group(1)
    except AttributeError:
        return resp.text

    # 获取敌人的怪物 ID，按照出场顺序排序，初始化战斗状态
    _, monster_ids = zip(*sorted(
        re.findall("Spawned Monster ([A-Z]): MID=([0-9]+)", resp.text),
        key=lambda x: x[0]  # 按照怪物出场的顺序排序，A 最先出场，B 第二个出场，以此类推
    ))
    enemy_list = [EnemyData() for _ in monster_ids]

    # 定义几个基础模板
    base_action_json = {"type": "battle", "method": "action", "token": battle_token}
    action_defend = base_action_json | {"mode": "defend", "target": 0, "skill": 0}
    action_item = base_action_json | {"mode": "items", "target": 0}

    # 定义请求+更新函数
    soups = {container_id: None for container_id in ["pane_vitals", "pane_monster", "pane_item", "table_magic", "pane_effects"]}
    def do_action(action: dict[str, Any]) -> list[dict[str, str]]:
        # 发送请求
        resp = request_with_retry(requests.post, f"{MAIN_URL}/{config.world}/json", json=action, **requests_kwargs)
        resp_json = resp.json()
        # 更新相应数据
        # 外挂的理想 API: 没有人机验证，而且 RESTful API
        # 最让我震惊的两件事: 没有人机验证（好！），以及都 2026 年了还在用后端返回 HTML 前端渲染的模式（坏！）
        for container_id in soups:
            if container_id in resp_json:
                soups[container_id] = BeautifulSoup(resp_json[container_id], "lxml")
        # 返回战斗记录
        return resp_json["textlog"]

    # 查询每个敌人的属性克制
    for i, monster_id in enumerate(monster_ids):
        # 如果查不到，就假设没有任何抗性
        if monster_id in database:
            enemy_list[i].resistance = database[monster_id]

    # 解析页面，初始化 soup
    soup = BeautifulSoup(resp.text, "lxml")
    soups = {container_id: soup.find(id=container_id) for container_id in soups}

    # 战斗循环
    while True:
        # 获取当前 buff，并补 buff
        effects = get_player_effects(soups)
        for effect_name, action in [
            ("Regeneration", action_item | {"skill": try_to_get_item_id("Health Draught", soups["pane_item"])}),
            ("Replenishment", action_item | {"skill": try_to_get_item_id("Mana Draught", soups["pane_item"])}),
            ("Regen", base_action_json | {"mode": "magic", "target": 0, "skill": try_to_get_magic_id("Regen", soups["table_magic"])})
        ]:
            # 仅在没有 buff 并且魔法/物品可用时使用
            # 有时候就是物品用完了、没钱买，或者等级太低没法使用这种魔法，所以得加个检测
            if effect_name not in effects and action["skill"] is not None:
                do_action(action)

        # 在战斗回合中，任何被击败的怪物都有约 4% 的几率掉落强化道具
        # 这些强化道具会自动放入玩家物品栏的“P”栏位。玩家一次只能拥有一个强化道具，并且必须使用当前道具才能获得新的强化道具
        # 强化道具在战斗回合之间保留，但在战斗结束后会消失，本质上是临时道具
        # 强化道具分 Mystic Gem, Health Gem, Mana Gem, Spirit Gem
        # Wiki: https://ehwiki.org/wiki/Items#Battle_Powerups
        # 消耗一下刷新出来的 Mystic Gem 和 Spirit Gem，它们对我没用
        for item_name in ["Mystic Gem", "Spirit Gem"]:
            if (item_id := try_to_get_item_id(item_name, soups["pane_item"])) is not None:
                do_action(action_item | {"skill": item_id})

        # 检测是否需要回血
        if get_player_health(soups) < config.safe_health_threshold:
            # 敌人在战斗中可能掉落一些特殊物品，优先使用。如果没有，那就使用玩家自带的蓝药
            # Potion 很便宜，但是得等 CD。Elixir 虽然也有 CD，但是和 Potion 的 CD 是独立的
            # 也就是说，可以先用 Potion 接着用 Elixir，他们的 CD 独立分开计算。但是 Elixir 很他妈贵。建议穷人打多点怪，攒多点 Credits 再买 
            for item_name in ["Health Gem", "Health Potion", "Health Elixir"]:
                if (item_id := try_to_get_item_id(item_name, soups["pane_item"])) is not None:
                    do_action(action_item | {"skill": item_id})
                    break
            else:
                # 如果回血药不可用，就尝试使用魔法 Cure
                # 如果 Cure 还在冷却，try_to_get_magic_id 就会返回 None，避免无意义的使用
                if (magic_id := try_to_get_magic_id("Cure", soups["table_magic"])) is not None:
                    do_action(base_action_json | {"mode": "magic", "target": 0, "skill": magic_id})
                else:
                    # 如果连 Cure 也在等 CD……我防御力不够，防御回血不够敌人攻击的多，所以还是等下面蓝回完了用 Cure 吧
                    print(f"[危险] 你的血量只有 {get_player_health(soups)} 这么少，但是你却没法使用回血药，也不能用魔法 Cure（当前蓝量 {get_player_mana(soups)}）")

        # 检测是否需要回蓝
        if get_player_mana(soups) < config.safe_mana_threshold:
            # 敌人在战斗中可能掉落一些特殊物品，优先使用
            # 如果没有，那就使用玩家自带的蓝药
            restore_mana_flag = False  # 我也想用 else，但是没有 break
            for item_name in ["Mana Gem", "Mana Potion", "Mana Elixir"]:
                if (item_id := try_to_get_item_id(item_name, soups["pane_item"])) is not None:
                    do_action(action_item | {"skill": item_id})
                    restore_mana_flag = True
                    break
            if restore_mana_flag:
                continue
            print(f"[危险] 你没有回蓝物品，蓝量只有 {get_player_mana(soups)}，血量只有 {get_player_health(soups)}")

        # 如果只有 1 个敌人存活，而且蓝量没有达到期望，那么在此阶段防御、等待药水效果回蓝，并顺带刷一下 CD
        update_enemy_data(enemy_list, soups)
        if sum(enemy.is_alive for enemy in enemy_list) == 1 and get_player_mana(soups) < config.end_battle_mana_target:
            do_action(action_defend)
            continue

        # 攻击阶段，计算攻击哪个目标的抗性和最小
        # 格式: ((目标, 魔法), (抗性和, 该属性的攻击消耗的魔法点数)
        attack_options = []
        for target_index in range(len(enemy_list)):
            # 你不能攻击一个死掉了的怪物
            if not enemy_list[target_index].is_alive:
                continue

            # 计算攻击目标和它旁边怪物的抗性总和，滑动窗口
            start = max(0, target_index - config.attack_target_range)
            end = min(len(enemy_list), target_index + config.attack_target_range + 1)
            window = enemy_list[start:end]

            # 各属性分别累加
            for magic in config.attack_magic_skills:
                resistance_sum = sum(
                    getattr(enemy.resistance, magic.attribute)
                    for enemy in window
                    if enemy.is_alive  # 只计算还活着的怪物的抗性
                )
                attack_options.append(((target_index, magic), (resistance_sum, magic.mana_cost)))

        # 选择抗性总和最小、消耗点数最少的攻击选项并执行攻击
        # 在游戏中，0 代表玩家本人，1 代表第一个怪物，2 代表第二个怪物，依此类推
        (best_target, best_magic), _ = min(attack_options, key=lambda x: x[1][0] + x[1][1] * config.mana_cost_weight)
        do_action(base_action_json | {"mode": "magic", "target": best_target + 1, "skill": try_to_get_magic_id(best_magic.name, soups["table_magic"])})

        # 打印信息
        update_enemy_data(enemy_list, soups)
        print(f"Alive Enemies: {sum(enemy.is_alive for enemy in enemy_list)}; HP: {get_player_health(soups)}; MP: {get_player_mana(soups)}; Effects: {get_player_effects(soups)}")

        # 如果所有敌人死亡，退出自动战斗
        if not any(enemy.is_alive for enemy in enemy_list):
            break


def main(args: argparse.Namespace):
    # 加载配置文件
    config = orjson.loads(args.config_file.read_bytes())
    config = BattleBotConfig.model_validate(config)

    # 加载怪兽属性抗性数据库
    database = {
        monster_id: MonsterResistanceData.model_validate(monster_info)
        for monster_id, monster_info in orjson.loads(args.database_file.read_bytes()).items()
    }

    # 准备 requests 用的参数
    requests_kwargs = dict(
        cookies={
            "ipb_member_id": config.ipb_member_id,
            "ipb_pass_hash": config.ipb_pass_hash
        },
        headers={
            "User-Agent": config.user_agent
        }
    )

    # 启动自动战斗
    progress_bar = tqdm(desc="自动战斗中", unit="场")
    while True:
        exception_html = auto_battle(config, database, requests_kwargs)
        if exception_html is not None:
            # 在 HentaiVerse 的任何战斗模式（血之环除外）中战斗时，玩家可能会随机遇到一个必须在限定时间内解决的谜题。
            # 选中图片中所有可见的小马，方法是勾选小马名称旁边的方框。
            # 玩家在规定时间内提交任何答案，无论正确与否，都将获得以下效果: 谜语大师的祝福（攻击力和魔法伤害暂时提高10%，持续 20 回合）
            # 在规定时间的前半段提交答案的玩家还将获得: 治疗效果，相当于生命宝石、魔法宝石和精神宝石的综合效果。
            # 如果错误过多，将会受到惩罚：战斗中体力消耗加快（惩罚的具体数值未公开）。
            # Wiki: https://ehwiki.org/wiki/RiddleMaster
            # 如果检测到这个函数，说明到了随机选小马的环节。我也想选对，但是我完全没看过小马宝莉
            # 还是 Google 一下，然后对照着选吧
            if "function check_submit_button() {" in exception_html:
                webbrowser.get("chrome").open(f"{MAIN_URL}/{config.world}")
                webbrowser.get("chrome").open("https://www.google.com/search?q=%E5%B0%8F%E9%A9%AC%E5%AE%9D%E8%8E%89+%E8%A7%92%E8%89%B2")
                input("选好了吗？回车以继续战斗")
                continue
            break
        progress_bar.update()
    progress_bar.close()


if __name__ == "__main__":
    main(parse_args())
