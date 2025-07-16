# -*- coding: utf-8 -*-

import json
import logging
from core.runner import APSRunner


def main():
    """
    应用程序主入口。
    """
    # 1. 在此统一配置整个应用的日志系统
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # 2. 加载配置文件
    settings_path = 'config/settings.json'
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    except FileNotFoundError:
        logging.error(f"致命错误: 配置文件未找到于 {settings_path}")
        return

    # 3. 初始化并运行 APSRunner
    try:
        runner = APSRunner(settings)
        runner.run()
    except Exception as e:
        logging.error("APSRunner 执行过程中发生未捕获的顶层异常: %s", e, exc_info=True)


if __name__ == "__main__":
    main()