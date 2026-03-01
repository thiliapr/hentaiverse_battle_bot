# thiliapr/hentaiverse_battle_bot
一个适用于 [HentaiVerse](https://hentaiverse.org/) 的自动打怪脚本，支持针对怪兽的各属性抗性特点，选择合适的攻击目标和攻击魔法攻击。

## 许可证
![GNU AGPL Version 3 Logo](https://www.gnu.org/graphics/agplv3-with-text-162x68.png)

thiliapr/hentaiverse_battle_bot 是自由软件，遵循 [Affero GNU 通用公共许可证第 3 版或任何后续版本](https://www.gnu.org/licenses/agpl-3.0.html)。你可以自由地使用、修改和分发。

## 这个工具有什么用
- 它可以让你开启一个[战斗](https://ehwiki.org/wiki/Battles)，然后让脚本自动打怪
- 你可以开 [GrindFest](https://hentaiverse.org/?s=Battle&ss=gr) 这种战斗（有 1000 场），然后在这里刷 [EXP](https://ehwiki.org/wiki/Experience_Points)、[熟练度](https://ehwiki.org/wiki/Proficiencies)、[物品](https://ehwiki.org/wiki/Items)、[装备](https://ehwiki.org/wiki/Equipment_Basics)和 [Credit](https://ehwiki.org/wiki/Credits)
- 你可以用它刷 Credit，然后在 [E-Hentai](https://e-hentai.org/) 下载 [Gallery](https://ehwiki.org/wiki/Galleries)。这种方式是完全免费的！

## 快速开始
### 你需要什么
- Python 3.10 或更高版本（因为使用了`Type | AnotherType`的联合类型写法）
- Chrome/Chromium 浏览器，并把`chrome.exe`所在目录加入 PATH 路径，推荐使用`ungoogled-chromium`，你可以从[Woolyss 的 Chromium Collection](https://chromium.woolyss.com/)下载预编译版本。你也可以使用其他浏览器，但是请修改`battle_bot.py`中的`webbrowser.get("chrome")`为你使用的浏览器，webbrowser 支持的浏览器列表见[文档](https://docs.python.org/zh-cn/3.14/library/webbrowser.html)
- 一个 E-Hentai 账号，点击[E-Hentai 登录](https://e-hentai.org/bounce_login.php?b=d&bt=1-1)注册或登录
- 这个账号对应的 HentaiVerse 必须达到可以使用至少一个攻击魔法的等级（[Wiki](https://ehwiki.org/wiki/Spells) 中说是 15 级，可以使用`Fiery Blast`）
- 带多点`Mana Draught`、`Health Draught`、`Mana Potion`、`Health Potion`（详情见 [Wiki](https://ehwiki.org/wiki/Items#Restoratives)），连续战斗时特别有用

### 安装
```bash
git clone https://github.com/thiliapr/hentaiverse_battle_bot.git
cd hentaiverse_battle_bot
python -m pip install -r requirements.txt
```

### 配置脚本
#### 注意事项
这个教程是为 [Chromium](https://www.chromium.org/) 而准备的，其他浏览器用户请按照自己的实际情况使用

#### 示例
```json
{
    "ipb_member_id": "19890604",
    "ipb_pass_hash": "deadbeefdeadbeefdeadbeefdeadbeef",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "attack_target_range": 2,
    "safe_health_threshold": 1400,
    "safe_mana_threshold": 110,
    "end_battle_mana_target": 220,
    "attack_magic_skills": [
        {"name": "Fiery Blast", "mana_cost": 5, "attribute": "fire"},
        {"name": "Freeze", "mana_cost": 5, "attribute": "cold"},
        {"name": "Shockblast", "mana_cost": 5, "attribute": "elec"},
        {"name": "Gale", "mana_cost": 5, "attribute": "wind"},
        {"name": "Smite", "mana_cost": 13, "attribute": "holy"}
    ],
    "world": ""
}
```

#### 流程
1. 首先，访问 <https://hentaiverse.org/>，如果你没有登录，请按照提示去登录
2. 登录完成后，访问 <https://hentaiverse.org/>，右键打开菜单，点击`检查`一项，在开发者工具找到`应用`一项，然后分别复制`ipb_member_id`和`ipb_pass_hash`值代替示例中的`ipb_member_id`和`ipb_pass_hash`
3. 点击`网络`选项，然后刷新一下页面，随便点击一个请求项，在详情中点击`标头`选项卡，往下翻到`请求标头`一项，找到其中的`User-Agent`项，把它的值复制过来，代替示例中的`user_agent`
4. 开启一场战斗，确保敌人足够多，然后用一个魔法攻击第一个目标，数一数多少个敌人受到了伤害，这个数字减去 1，就是示例中的`attack_target_range`（除了指定了的目标外，你还可以攻击目标周围多少个怪兽）
5. `safe_health_threshold`、`safe_mana_threshold`和`end_battle_mana_target`需要根据自己的实际情况和经验设置
6. `attack_magic_skills`填写你目前可用的攻击魔法。需要提供在游戏中的显示名称、魔法的属性，以及该魔法消耗的蓝量。你可以开启一场战斗，然后点击 UI 上方的`SKILLBOOK`，然后点击出现在下方的 `SPELLS` 查看你能用你的攻击魔法的名称、攻击属性和耗蓝量。属性包括`["fire", "cold", "elec", "wind", "holy", "dark"]`这六种。如果你发现你没有对应的魔法，别担心，大概只是你没有达到相应等级而已。各个魔法的解锁等级见 [Wiki](https://ehwiki.org/wiki/Spells)
7. `world`的值有两个: 空和`isekai`。详情请参见 [Wiki](https://ehwiki.org/wiki/Isekai)
8. 将所有项目配置完成后，将配置文件保存到一个地方

### 运行
#### 流程
1. 首先，你需要下载怪兽抗性数据库。运行`python update_database.py monster_resistance_data.json`以下载最新数据库，这里使用 [Wiki](https://ehwiki.org/wiki/Monster_Lab) 中`See Also`的[zhenterzzf and OnceForAll's Monster Database](https://hv-monster.skk.moe/)作为数据源
2. 首先，你要在浏览器打开一场战斗，比如 [GrindFest](https://hentaiverse.org/?s=Battle&ss=gr)
3. 确保配置无误后，运行 `python battle_bot.py --config-file ${config_file_path} --database-file monster_resistance_data.json`，`${config_file_path}` 为你刚才在`配置脚本`时保存的路径
4. 你可能需要在电脑前等候，因为战斗时可能遇到[小马谜题](https://ehwiki.org/wiki/RiddleMaster)，需要你根据图片选择对应的小马宝莉中的小马，并且如果错误率太高会有体力惩罚。程序遇到小马谜题时会打开浏览器两个页面，一个是`小马宝莉 角色`的搜索，另一个是谜题页面，你可以对照搜索结果选择

#### 简单示例
```bash
python update_database.py monster_resistance_data.json
python battle_bot.py --config-file /path/to/config.json --database-file monster_resistance_data.json
```
