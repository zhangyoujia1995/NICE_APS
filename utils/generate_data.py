# -*- coding: utf-8 -*-

import json
import random
import os
from typing import List, Dict
from datetime import datetime, timedelta

# --- 1. 配置生成参数 ---
# 您可以在这里调整，以生成不同特性和规模的数据
CONFIG = {
    "num_factories": 20,
    "num_orders": 3000,
    "factory_output_path": r"E:\Projects\NICE_APS/data/test_factories.json",
    "order_output_path": r"E:\Projects\NICE_APS/data/test_orders.json",
    "base_start_date": "2025-08-01",
    "num_periods": 16,  # 生成大约6个月的周期（13 * 2周）
    "period_duration_days": 14, # 定义每个周期的天数（14天 = 2周）
    "order_quantity_min": 500,     # 新增：订单最小数量
    "order_quantity_max": 1500,    # 新增：订单最大数量
    "regions": ["CHINA", "VIETNAM", "CAMBODIA", "THAILAND"],
    "product_types": ["外套", "裤子", "衬衫"],
    "all_processes": {
        "裁剪": {"base_capacity": 30000, "volatility": 0.15},
        "缝纫": {"base_capacity": 40000, "volatility": 0.15}
    },
    "cutting_process_probability": 0.7  # 定义裁剪工序的拥有概率
}


def save_data_to_json(data_to_save: List[Dict], output_path: str):
    """
    将列表数据以JSON格式保存到指定文件。
    会自动创建不存在的目录。
    """
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir:  # 只有当路径包含目录时才创建
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        print(f"数据成功保存至: '{output_path}'")
    except Exception as e:
        print(f"写入文件 '{output_path}' 时发生错误: {e}")


def generate_factories_data():
    """
    程序化地生成具有多样性的工厂测试数据，并保存为JSON文件。
    """
    factories_data = []
    # 新增：区域计数器，用于为每个区域独立编号
    region_counters = {}

    for _ in range(CONFIG["num_factories"]):
        # --- a. 变更：根据新规则生成工厂ID ---
        region = random.choice(CONFIG["regions"])

        # 获取当前区域的计数，并加1
        current_count = region_counters.get(region, 0) + 1
        # 更新计数器
        region_counters[region] = current_count

        # 使用区域专属的计数来生成ID
        factory_id = f"F_{region[:2]}_{current_count:02d}"

        # --- b. 根据新规则为工厂分配工序 ---
        factory_processes = ["缝纫"]
        if random.random() < CONFIG["cutting_process_probability"]:
            factory_processes.append("裁剪")

        # --- c. 为工厂的每个产品线生成随机的生产效率档位 ---
        efficiencies = {}
        for p_type in CONFIG["product_types"]:
            tiers = []
            # 随机决定生成2档还是3档
            num_tiers = random.choice([2, 3])

            # 为该产品线设定一个基础效率，后续档位在此基础上浮动
            base_eff = random.uniform(0.60, 0.85)

            # 初始化第一个档位的最小数量和效率
            current_min_quantity = 0
            current_efficiency = base_eff * random.uniform(0.9, 1.0)  # 第一档效率最低

            for tier_index in range(num_tiers):
                # 确定当前档位的数量区间
                min_q = current_min_quantity

                # 如果是最后一档，最大数量设为一个很大的值
                if tier_index == num_tiers - 1:
                    max_q = 99999
                else:
                    # 随机生成分界点
                    boundary = random.randint(min_q + 1500, min_q + 3000)
                    max_q = boundary - 1

                tiers.append({
                    "min_quantity": min_q,
                    "max_quantity": max_q,
                    "efficiency": round(current_efficiency, 2)
                })

                # 为下一个档位更新起始数量和效率
                current_min_quantity = max_q + 1
                # 确保下一档的效率比当前档位高
                current_efficiency *= random.uniform(1.01, 1.08)

            efficiencies[p_type] = tiers

        # --- d. 为工厂生成未来所有周期的产能 ---
        periods = []
        current_start_date = datetime.strptime(CONFIG["base_start_date"], "%Y-%m-%d").date()
        for _ in range(CONFIG["num_periods"]):
            # 变更：使用配置项来计算结束日期
            # 减1是因为周期包含了开始那天，例如14天的周期，结束日期是开始日期之后的13天
            end_date = current_start_date + timedelta(days=CONFIG["period_duration_days"] - 1)

            capacity_by_process = {}
            for proc_name in factory_processes:
                proc_info = CONFIG["all_processes"][proc_name]
                base_cap = proc_info["base_capacity"]
                vol = proc_info["volatility"]
                randomized_capacity = int(base_cap * (1 + random.uniform(-vol, vol)))
                capacity_by_process[proc_name] = randomized_capacity

            periods.append({
                "start_date": current_start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "capacity_by_process": capacity_by_process
            })

            current_start_date = end_date + timedelta(days=1)

        # --- e. 组装成一个完整的工厂对象 ---
        factory = {
            "factory_id": factory_id,
            "region": region,
            "production_efficiencies": efficiencies,
            "capacity_periods": periods
        }
        factories_data.append(factory)

    return factories_data


def generate_orders_data(factories: List[Dict]):
    """根据生成的工厂数据，程序化地生成合理的订单数据。"""
    orders_data = []

    for i in range(CONFIG["num_orders"]):
        order_id = f"TEST_{i + 1:03d}"
        product_type = random.choice(CONFIG["product_types"])
        quantity = random.randint(CONFIG["order_quantity_min"], CONFIG["order_quantity_max"])

        # --- b. 智能确定订单所需工序和合格工厂 ---
        required_processes = {"缝纫"}  # 所有订单都需要缝纫
        if random.random() < 0.8:  # 80%的订单需要裁剪
            required_processes.add("裁剪")

        capable_factories = []
        for factory in factories:
            # set(factory_processes) >= required_processes 判断工厂的工序是否包含订单所需的所有工序
            factory_processes = factory["capacity_periods"][0]["capacity_by_process"].keys()
            if set(factory_processes).issuperset(required_processes):
                capable_factories.append(factory["factory_id"])

        # 如果找不到能做的工厂，就跳过这个订单的生成
        if not capable_factories:
            continue

        # --- c. 生成订单其他属性 ---
        due_date = datetime.strptime(CONFIG["base_start_date"], "%Y-%m-%d").date() + timedelta(
            days=random.randint(60, 240))
        total_process_capacity = {}
        if "裁剪" in required_processes:
            total_process_capacity["裁剪"] = int(quantity * random.uniform(0.8, 1.2))
        if "缝纫" in required_processes:
            total_process_capacity["缝纫"] = int(quantity * random.uniform(1.2, 1.8))

        order = {
            "order_id": order_id,
            "customer": f"客户_{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}",
            "product_type": product_type,
            "style": f"{product_type}-款{random.randint(1, 100)}",
            "quantity": quantity,
            "due_date": due_date.strftime("%Y-%m-%d"),
            "material_purchasing_lead_time": random.randint(10, 30),
            "material_transportation_to_region_lead_time": {
                region: random.randint(20, 50) for region in CONFIG["regions"]
            },
            "production_lead_time": random.randint(3, 8),
            "total_process_capacity": total_process_capacity,
            "eligible_factories": capable_factories
        }
        orders_data.append(order)

    return orders_data


if __name__ == '__main__':
    # 步骤1：生成工厂数据
    print("--- 步骤 1: 开始生成工厂数据 ---")
    generated_factories = generate_factories_data()
    # 步骤2：将生成的工厂数据保存到文件
    save_data_to_json(generated_factories, CONFIG["factory_output_path"])

    print("\n--- 步骤 2: 开始生成订单数据 ---")
    # 步骤3：在内存中生成订单数据
    generated_orders = generate_orders_data(generated_factories)
    # 步骤4：将生成的订单数据保存到文件
    save_data_to_json(generated_orders, CONFIG["order_output_path"])

    print("\n数据生成完毕！")