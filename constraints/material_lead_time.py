# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from ortools.sat.python import cp_model
from core.process_data import APSInputData
from core.variable_registry import VariableDict


def add_material_lead_time_constraint(
        model: cp_model.CpModel,
        data: APSInputData,
        variables: VariableDict
):
    logging.info("开始添加“物料前置时间”显式约束...")

    constraints_added = 0

    for order_id, factory_vars in variables.items():
        order = data.order_map[order_id]

        for factory_id, period_vars in factory_vars.items():
            factory = data.factory_map[factory_id]

            transport_lt = order.material_transportation_to_region_lead_time.get(factory.region, float('inf'))
            total_lt_days = (
                    order.material_purchasing_lead_time +
                    transport_lt +
                    order.production_lead_time
            )
            earliest_start_date = data.base_date + timedelta(days=total_lt_days)

            for period_start_date_str, var in period_vars.items():
                period_start_date_obj = datetime.strptime(period_start_date_str, '%Y-%m-%d').date()

                if period_start_date_obj < earliest_start_date:
                    model.Add(var == 0)
                    constraints_added += 1

    logging.info(f"“物料前置时间”约束添加完成。共添加了 {constraints_added} 条强制为0的约束。")