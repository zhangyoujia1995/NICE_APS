# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, List
from dataclasses import dataclass

# 引入 OR-Tools 的核心模型库和我们定义的数据结构
from ortools.sat.python import cp_model
from core.process_data import APSInputData, _get_efficiency_for_order
from core.variable_registry import VariableDict
from .load_data import Order

# --- 标准化的单条排程结果容器 ---
@dataclass
class ScheduleResultItem:
    """用于存放一条完整、已解析的排程结果的数据类。"""
    order: Order
    assigned_factory_id: str
    assigned_period_start: str
    assigned_period_end: str
    is_tardy: bool
    days_tardy: int
    material_ready_date: date
    latest_confirmation_date: date


def calculate_and_log_kpis(
        schedule_results: List[ScheduleResultItem],
        data: APSInputData
):
    """
    计算并记录关键性能指标(KPI)，例如工厂负载率。

    Args:
        solver (cp_model.CpSolver): 已求解的求解器实例。
        data (APSInputData): 预处理后的数据容器。
        variables (VariableDict): 决策变量字典。
    """
    # --- 1. 交付表现 (Delivery Performance) KPI ---
    logging.info("="*20 + " 7. 计算并输出KPI " + "="*20)
    print("-" * 80)
    logging.info("--- 交付表现 (Delivery Performance) ---")

    total_orders = len(schedule_results)
    tardy_orders_count = sum(1 for result in schedule_results if result.is_tardy)

    if total_orders > 0:
        on_time_rate = (total_orders - tardy_orders_count) / total_orders
        logging.info(f"  - 总排程订单数: {total_orders}")
        logging.info(f"  - 延误订单数:   {tardy_orders_count}")
        logging.info(f"  - 准时交付率:   {on_time_rate:.1%}")
    else:
        logging.info("  - 没有已排程的订单。")

    # --- 2. 工厂周期性负载率 KPI ---
    logging.info("工厂周期性负载率 (已分配工作量 / 总产能):")

    # 构建一个字典来快速查找每个周期的工作量
    workload_by_period = {}
    for result in schedule_results:
        key = (result.assigned_factory_id, result.assigned_period_start)
        factory = data.factory_map[result.assigned_factory_id]
        efficiency = _get_efficiency_for_order(result.order, factory)
        base_workload = data.order_total_base_workload[result.order.order_id]
        actual_workload = int(base_workload / efficiency)
        workload_by_period[key] = workload_by_period.get(key, 0) + actual_workload

    for factory in data.factories:
        factory_id = factory.factory_id
        logging.info(f"\n  --- 工厂: {factory_id} ---")
        for period in factory.capacity_periods:
            period_start_date = period.start_date
            total_capacity = data.factory_total_capacity_by_period.get(factory_id, {}).get(period_start_date, 0)
            assigned_workload = workload_by_period.get((factory_id, period_start_date), 0)

            if total_capacity > 0:
                load_rate = assigned_workload / total_capacity
                logging.info(
                    f"    - 周期 {period_start_date}: {load_rate:.1%} (已分配: {assigned_workload} / 总计: {int(total_capacity)})")
            else:
                logging.info(f"    - 周期 {period_start_date}: 0.0% (总产能为 0)")


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

    if solver.StatusName() not in ('OPTIMAL', 'FEASIBLE'):
        logging.warning("模型无解或求解失败，无排程结果可输出。")
        return

    # --- 步骤1：将求解器的原始结果解析为标准的排程结果列表 ---
    schedule_results: List[ScheduleResultItem] = []
    period_end_date_map = {f.factory_id: {p.start_date: p.end_date for p in f.capacity_periods} for f in data.factories}

    for order_id, factory_vars in variables.items():
        is_assigned = False
        for factory_id, period_vars in factory_vars.items():
            for period_start_date_str, var in period_vars.items():
                if solver.Value(var) == 1:
                    order_obj = data.order_map[order_id]
                    factory_obj = data.factory_map[factory_id]

                    # 进行日期转换和计算
                    completion_date_obj = datetime.strptime(period_end_date_map[factory_id][period_start_date_str],
                                                            '%Y-%m-%d').date()
                    due_date_obj = datetime.strptime(order_obj.due_date, '%Y-%m-%d').date()
                    period_start_date_obj = datetime.strptime(period_start_date_str, '%Y-%m-%d').date()

                    # 计算延误情况
                    is_tardy = completion_date_obj > due_date_obj
                    days_tardy = (completion_date_obj - due_date_obj).days if is_tardy else 0

                    # 计算关键日期
                    material_ready_date = period_start_date_obj - timedelta(days=order_obj.production_lead_time)
                    transport_lt = order_obj.material_transportation_to_region_lead_time.get(factory_obj.region, 0)
                    latest_confirmation_date = material_ready_date - timedelta(
                        days=order_obj.material_purchasing_lead_time + transport_lt)

                    # 创建并填充结果对象
                    result_item = ScheduleResultItem(
                        order=order_obj,
                        assigned_factory_id=factory_id,
                        assigned_period_start=period_start_date_str,
                        assigned_period_end=period_end_date_map[factory_id][period_start_date_str],
                        is_tardy=is_tardy,
                        days_tardy=days_tardy,
                        material_ready_date=material_ready_date,
                        latest_confirmation_date=latest_confirmation_date
                    )
                    schedule_results.append(result_item)
                    is_assigned = True
                    break
            if is_assigned:
                break

        if not is_assigned:
            logging.warning(f"  [-] 订单 '{order_id}' 未找到分配方案。")

    # --- 步骤2：基于解析后的结果列表，打印详细日志 ---
    # logging.info("模型找到可行解，详细排程结果如下:")
    # print("-" * 80)
    # for result in schedule_results:
    #     tardy_info = f" (延误 {result.days_tardy} 天!)" if result.is_tardy else ""
    #     log_msg = (
    #         f"  [+] 订单 '{result.order.order_id}' (数量: {result.order.quantity}, 要求交期: {result.order.due_date}{tardy_info})\n"
    #         f"      ├── 分配至: 工厂='{result.assigned_factory_id}', 生产周期: {result.assigned_period_start} to {result.assigned_period_end}\n"
    #         f"      └── 关键日期: 物料就绪日='{result.material_ready_date.strftime('%Y-%m-%d')}', 最晚确认日='{result.latest_confirmation_date.strftime('%Y-%m-%d')}'"
    #     )
    #     logging.info(log_msg)
    # print("-" * 80)
    logging.info(f"总共为 {len(schedule_results)} / {len(data.orders)} 个订单找到了排程。")
    logging.info(f"最终目标值: {solver.ObjectiveValue()}")

    # --- 步骤3：基于解析后的结果列表，计算和打印KPI ---
    calculate_and_log_kpis(schedule_results, data)