# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta  # 引入 timedelta 用于日期计算
from typing import Dict, Any

# 引入 OR-Tools 的核心模型库和我们定义的数据结构
from ortools.sat.python import cp_model
from core.process_data import APSInputData
from core.variable_registry import VariableDict


def process_and_log_results(
        solver: cp_model.CpSolver,
        data: APSInputData,
        variables: VariableDict
):
    """
    处理并输出求解结果。
    当前版本将包含关键日期的详细排程信息打印到日志中。

    Args:
        solver (cp_model.CpSolver): 已经完成求解的求解器实例。
        data (APSInputData): 包含了所有预处理后数据的容器。
        variables (VariableDict): 包含了所有决策变量的嵌套字典。
    """
    logging.info("=" * 20 + " 6. 解析并输出结果 " + "=" * 20)

    if solver.StatusName() in ('OPTIMAL', 'FEASIBLE'):
        logging.info("模型找到可行解，排程结果如下:")
        print("-" * 80)

        assigned_orders_count = 0

        period_end_date_map = {
            f.factory_id: {p.start_date: p.end_date for p in f.capacity_periods}
            for f in data.factories
        }

        for order_id, factory_vars in variables.items():
            is_assigned = False
            order_obj = data.order_map[order_id]

            for factory_id, period_vars in factory_vars.items():
                factory_obj = data.factory_map[factory_id]

                for period_start_date_str, var in period_vars.items():
                    if solver.Value(var) == 1:
                        # --- 提取基础信息 ---
                        quantity = order_obj.quantity
                        due_date_str = order_obj.due_date
                        region = factory_obj.region
                        period_end_date_str = period_end_date_map[factory_id][period_start_date_str]

                        # --- 进行日期转换和计算 ---
                        period_start_date_obj = datetime.strptime(period_start_date_str, '%Y-%m-%d').date()
                        completion_date_obj = datetime.strptime(period_end_date_str, '%Y-%m-%d').date()
                        due_date_obj = datetime.strptime(due_date_str, '%Y-%m-%d').date()

                        # 1. 计算物料就绪日期 (Material Ready Date)
                        #    公式: 订单开始日期(周期开始) - 生产提前期
                        material_ready_date = period_start_date_obj - timedelta(days=order_obj.production_lead_time)

                        # 2. 计算物料确认最晚日期 (Latest Material Confirmation Date)
                        #    公式: 物料就绪日期 - (采购LT + 运输LT)
                        purchasing_lt = order_obj.material_purchasing_lead_time
                        transport_lt = order_obj.material_transportation_to_region_lead_time.get(region, 0)
                        latest_confirmation_date = material_ready_date - timedelta(days=purchasing_lt + transport_lt)

                        # --- 延误判断 ---
                        tardy_info = " (延误!)" if completion_date_obj > due_date_obj else ""

                        # --- 构建并记录丰富化的日志 ---
                        log_msg = (
                            f"  [+] 订单 '{order_id}' (数量: {quantity}, 要求交期: {due_date_str}{tardy_info})\n"
                            f"      ├── 分配至: 工厂='{factory_id}' (区域: {region}), 生产周期: {period_start_date_str} to {period_end_date_str}\n"
                            f"      └── 关键日期: 物料就绪日='{material_ready_date.strftime('%Y-%m-%d')}', 最晚确认日='{latest_confirmation_date.strftime('%Y-%m-%d')}'"
                        )
                        logging.info(log_msg)

                        is_assigned = True
                        assigned_orders_count += 1
                        break
                if is_assigned:
                    break

            if not is_assigned:
                logging.warning(f"  [-] 订单 '{order_id}' 未找到分配方案。")

        print("-" * 80)
        logging.info(f"总共为 {assigned_orders_count} / {len(data.orders)} 个订单找到了排程。")
        logging.info(f"最终目标值: {solver.ObjectiveValue()}")

    else:
        logging.warning("模型无解或求解失败，无排程结果可输出。")