# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any, Optional, Tuple

# 引入所有核心组件
from .load_data import load_and_structure_data
from .process_data import process_data
from .variable_registry import create_variables, VariableDict
from .solver import SATSolver
from ortools.sat.python import cp_model
from .store_result import process_and_save_results

# --- 引入所有约束和目标模块 ---
# 约束
from constraints.order_unique_assign import add_order_unique_assign_constraint
from constraints.capacity import add_capacity_constraint
from constraints.material_lead_time import add_material_lead_time_constraint
# 目标
from objectives.combined_objective import set_combined_objective

# --- 创建约束映射表 ---
# key: settings.json中 active_constraints 列表里的字符串
# value: 对应的要执行的函数
CONSTRAINT_MAP = {
    "order_unique_assign": add_order_unique_assign_constraint,
    "capacity": add_capacity_constraint,
    "material_lead_time": add_material_lead_time_constraint
}


class APSRunner:
    """
    APS系统的核心流程执行器。
    负责按顺序调用数据处理、模型构建和求解等所有模块。
    """

    def __init__(self, settings: Dict[str, Any]):
        """
        初始化执行器。
        Args:
            settings (Dict[str, Any]): 从 settings.json 加载的配置字典。
        """
        self.settings = settings
        logging.info("APSRunner 已初始化。")

    def _data_pipeline(self) -> bool:
        """执行数据管道：加载和预处理数据。"""
        logging.info("=" * 20 + " 1. 执行数据管道 " + "=" * 20)
        try:
            factories, orders = load_and_structure_data(self.settings)
            self.aps_input_data = process_data(factories, orders, self.settings)
            return True
        except Exception as e:
            logging.error(f"数据管道执行过程中发生错误: {e}", exc_info=True)
            return False

    def _initialize_model(self) -> Optional[Tuple[cp_model.CpModel, VariableDict, SATSolver]]:
        """初始化求解器、模型和决策变量。"""
        logging.info("=" * 20 + " 2. 初始化求解器与变量 " + "=" * 20)
        try:
            sat_solver = SATSolver(self.settings)
            model = sat_solver.get_model()
            variables = create_variables(model, self.aps_input_data)
            return model, variables, sat_solver
        except Exception as e:
            logging.error(f"求解器初始化或变量创建时发生错误: {e}", exc_info=True)
            return None

    def _add_constraints(self, model: cp_model.CpModel, variables: VariableDict):
        """动态添加所有激活的约束。"""
        logging.info("=" * 20 + " 3. 添加约束 " + "=" * 20)
        active_constraints = self.settings.get('active_constraints', [])
        logging.info(f"激活的约束列表: {active_constraints}")

        for constraint_name in active_constraints:
            constraint_func = CONSTRAINT_MAP.get(constraint_name)
            if constraint_func:
                constraint_func(model, self.aps_input_data, variables)
            else:
                logging.warning(f"配置中请求的约束 '{constraint_name}' 没有找到对应的实现模块，已跳过。")

    def _set_objective(self, model: cp_model.CpModel, variables: VariableDict):
        """设置组合优化目标。"""
        logging.info("=" * 20 + " 4. 添加优化目标 " + "=" * 20)
        set_combined_objective(model, self.aps_input_data, variables)

    def _solve_model(self, sat_solver: SATSolver) -> cp_model.CpSolver:
        """调用求解器进行求解。"""
        logging.info("=" * 20 + " 5. 开始求解 " + "=" * 20)
        return sat_solver.solve()

    def _process_results(self, solver_instance: cp_model.CpSolver, variables: VariableDict):
        """处理并输出结果。"""
        process_and_save_results(solver_instance, self.aps_input_data, variables)

    def run(self):
        """
        执行端到端的APS计算流程。
        """
        logging.info("APS 核心流程开始执行...")

        # --- 1. 数据管道 ---
        if not self._data_pipeline():
            logging.error("数据处理失败，流程终止。")
            return

        # --- 2. 求解器初始化与变量创建 ---
        init_result = self._initialize_model()
        if not init_result:
            logging.error("模型初始化失败，流程终止。")
            return
        model, variables, sat_solver = init_result

        # --- 3. 动态添加约束 ---
        self._add_constraints(model, variables)

        # --- 4. 添加组合优化目标 ---
        self._set_objective(model, variables)

        # --- 5. 求解 ---
        solver_instance = self._solve_model(sat_solver)

        # --- 6. 存储结果 (未来步骤) ---
        self._process_results(solver_instance, variables)

        logging.info("APS 执行完毕。")