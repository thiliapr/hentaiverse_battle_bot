# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 thiliapr <thiliapr@tutanota.com>
# SPDX-Package: hentaiverse_battle_bot
# SPDX-PackageHomePage: https://github.com/thiliapr/hentaiverse_battle_bot

import pathlib
import argparse
import subprocess
import orjson

# 只储存魔法抗性，因为我主修魔法，物理抗性数据于我无用
USED_FIELDS = {
    "cold",
    "wind",
    "elec",
    "fire",
    "holy",
    "dark",
}


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--database-file", type=pathlib.Path, default=pathlib.Path("monster_resistance_data.json"), help="怪物数据库文件路径")
    return parser.parse_args(args)


def main(args: argparse.Namespace):
    # 调用 curl 获取远程数据库
    process = subprocess.run(["curl", "-o", "-", "https://hv-monsterdb-data.skk.moe/persistent.json"], check=True, capture_output=True)

    remote_database = orjson.loads(process.stdout)
    remote_database = {monster["monsterId"]: monster for monster in remote_database}

    # 只保留需要的字段
    updated_database = {
        str(monster_id): {
            k: v
            for k, v in monster_data.items()
            if k in USED_FIELDS
        }
        for monster_id, monster_data in remote_database.items()
    }

    # 保存更新后的数据库
    args.database_file.write_bytes(orjson.dumps(updated_database, option=orjson.OPT_INDENT_2))


if __name__ == "__main__":
    main(parse_args())
