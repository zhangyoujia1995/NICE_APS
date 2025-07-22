# -*- coding: utf-8 -*-

import logging
import os
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Dict, Any, List
from dataclasses import dataclass

# 引入 OR-Tools 的核心模型库和我们定义的数据结构
from ortools.sat.python import cp_model
from core.process_data import APSInputData, _get_efficiency_for_order
from core.variable_registry import VariableDict
from .load_data import Order
from utils.file_handler import save_data_to_json

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


def calculate_and_save_kpis(
        schedule_results: List[ScheduleResultItem],
        data: APSInputData,
        settings: Dict[str, Any]
):
    """
    计算KPI，并将结果保存为JSON文件。
    """
    output_path = settings.get("output_paths", {}).get("kpi_output_path")
    if not output_path:
        logging.warning("配置文件中未指定 'kpi_output_path'，跳过KPI文件保存。")
        return

    logging.info(f"开始计算KPI并准备保存到: {output_path} ...")

    kpi_results = {}
    workload_by_period = {}
    for r in schedule_results:
        key = (r.assigned_factory_id, r.assigned_period_start)
        factory = data.factory_map[r.assigned_factory_id]
        efficiency = _get_efficiency_for_order(r.order, factory)
        base_workload = data.order_total_base_workload[r.order.order_id]
        actual_workload = int(base_workload / efficiency)
        workload_by_period[key] = workload_by_period.get(key, 0) + actual_workload

    for factory in data.factories:
        factory_id = factory.factory_id
        period_load_rates = []
        load_rate_by_period_dict = {}

        for period in factory.capacity_periods:
            period_start_date = period.start_date
            total_capacity = data.factory_total_capacity_by_period.get(factory_id, {}).get(period_start_date, 0)
            assigned_workload = workload_by_period.get((factory_id, period_start_date), 0)
            load_rate = (assigned_workload / total_capacity) if total_capacity > 0 else 0

            period_load_rates.append(load_rate)
            load_rate_by_period_dict[period_start_date] = round(load_rate, 3)

        # 计算新的KPI统计值
        active_period_rates = [r for r in period_load_rates if r > 0]
        max_load = max(period_load_rates) if period_load_rates else 0
        min_load_active = min(active_period_rates) if active_period_rates else 0
        avg_load = sum(period_load_rates) / len(period_load_rates) if period_load_rates else 0

        kpi_results[factory_id] = {
            "max_load_rate": round(max_load, 3),
            "min_load_rate_active_periods": round(min_load_active, 3),
            "average_load_rate": round(avg_load, 3),
            "load_rate_by_period": load_rate_by_period_dict
        }

    # 调用通用函数保存KPI JSON文件
    save_data_to_json(kpi_results, output_path)


# --- 将结果保存为csv文件的函数 ---
def save_schedule_to_csv(
        schedule_results: List[ScheduleResultItem],
        data: APSInputData,
        settings: Dict[str, Any]
):
    """
    将详细排程结果保存为CSV文件。
    """
    output_path = settings.get("output_paths", {}).get("csv_result_path")
    if not output_path:
        logging.warning("配置文件中未指定 'csv_result_path'，跳过CSV文件保存。")
        return
    if not schedule_results:
        logging.info("没有排程结果可供保存。")
        return

    rows_data = []
    for r in schedule_results:
        due_date_obj = datetime.strptime(r.order.due_date, '%Y-%m-%d').date()
        completion_date_obj = datetime.strptime(r.assigned_period_end, '%Y-%m-%d').date()

        # 新增列的计算
        deviation_days = abs((due_date_obj - completion_date_obj).days)

        rows_data.append({
            "订单ID": r.order.order_id,
            "客户": r.order.customer,
            "订单数量": r.order.quantity,
            "要求交期": r.order.due_date,
            "分配工厂ID": r.assigned_factory_id,
            "工厂区域": data.factory_map[r.assigned_factory_id].region,
            "计划完成日期": r.assigned_period_end,
            "是否延误": "是" if r.is_tardy else "否",
            "与交期偏差天数": deviation_days,
            "物料就绪日期": r.material_ready_date.strftime('%Y-%m-%d'),
            "物料最晚确认日期": r.latest_confirmation_date.strftime('%Y-%m-%d')
        })

    try:
        df = pd.DataFrame(rows_data)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logging.info(f"排程结果已成功保存到: {output_path}")
    except Exception as e:
        logging.error(f"保存CSV文件时发生错误: {e}", exc_info=True)


def process_and_save_results(
        solver: cp_model.CpSolver,
        data: APSInputData,
        variables: VariableDict
):
    """
    解析、记录日志、并保存所有结果（排程表和KPI）。

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

    # --- 步骤2：基于解析后的结果列表 ---
    logging.info(f"总共为 {len(schedule_results)} / {len(data.orders)} 个订单找到了排程。")
    logging.info(f"最终目标值: {solver.ObjectiveValue()}")

    # --- 步骤3：保存详细排程到CSV ---
    save_schedule_to_csv(schedule_results, data, data.settings)

    # --- 步骤4：计算并保存KPI到JSON ---
    calculate_and_save_kpis(schedule_results, data, data.settings)