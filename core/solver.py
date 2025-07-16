# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any

# 引入 OR-Tools 的核心模型和求解器库
from ortools.sat.python import cp_model


class SATSolver:
    """
    一个对 OR-Tools CP-SAT 求解器的封装类。
    负责模型的初始化、求解过程的调用以及结果状态的记录。
    """

    def __init__(self, settings: Dict[str, Any]):
        """
        初始化求解器。

        Args:
            settings (Dict[str, Any]): 从 settings.json 加载的配置字典。
        """
        # 1. 创建 CP-SAT 模型实例。
        #    这可以被看作是我们将要构建所有变量和约束的“画布”。
        self.model = cp_model.CpModel()

        # 2. 创建求解器实例。
        #    这是执行求解过程的“引擎”。
        self.solver = cp_model.CpSolver()

        # 设置此参数为 True，求解器将在求解过程中打印详细的日志。
        self.solver.parameters.log_search_progress = True
        # 设置并行求解的核心数量
        self.solver.parameters.num_search_workers = 8

        # 3. 从配置文件中读取并设置求解器参数。
        #    例如，设置求解时间上限，防止求解过程无限进行。
        time_limit = settings.get('run_config', {}).get('solver_time_limit_seconds', 60)
        self.solver.parameters.max_time_in_seconds = time_limit

        logging.info(f"求解器已初始化。求解时间上限设置为: {time_limit} 秒。")

    def get_model(self) -> cp_model.CpModel:
        """
        获取模型实例。
        其他模块（如变量注册表、约束模块）将需要这个模型实例来添加变量和约束。

        Returns:
            cp_model.CpModel: CP-SAT 模型实例。
        """
        return self.model

    def solve(self) -> cp_model.CpSolver:
        """
        执行求解过程。

        Returns:
            cp_model.CpSolver: 完成求解后的求解器实例。
                               可以通过它获取解的状态、目标值和变量值。
        """
        logging.info("开始求解模型...")

        # 调用 OR-Tools 的核心求解方法
        status = self.solver.Solve(self.model)

        logging.info("求解结束。")

        # --- 根据求解状态，记录不同的日志信息 ---
        if status == cp_model.OPTIMAL:
            logging.info("成功找到最优解！")
            logging.info(f"最优目标值: {self.solver.ObjectiveValue()}")
        elif status == cp_model.FEASIBLE:
            # 在有时间限制的情况下，找到可行解但未证明其为最优解是常见情况
            logging.info("在时间限制内成功找到一个可行解（不一定是最优解）。")
            logging.info(f"可行解的目标值: {self.solver.ObjectiveValue()}")
        elif status == cp_model.INFEASIBLE:
            logging.error("模型无解。请检查约束条件是否存在冲突。")
        elif status == cp_model.MODEL_INVALID:
            logging.error("模型无效。请检查模型的定义是否正确。")
        else:
            logging.warning("求解状态未知。")

        logging.info(f"求解耗时: {self.solver.WallTime()} 秒")

        # 返回求解器实例，其中包含了所有的解信息
        return self.solver