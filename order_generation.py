import random
import json
from datetime import datetime, timedelta

# 固定种子便于结果可复现
random.seed(42)

# 预设数据
customers = [f"客户{c}" for c in "ABCDEFGHIJKLMN"]
product_types = ["外套", "衬衫", "裤子"]
style_prefix = {"外套": ["AW25", "SS26"], "衬衫": ["SS26", "AW25"], "裤子": ["SS26", "AW25"]}
style_names = {
    "外套": ["风衣", "大衣", "夹克", "冲锋衣", "皮衣", "羽绒服"],
    "衬衫": ["长袖衬衫", "短袖衬衫", "法兰绒", "POLO"],
    "裤子": ["工装裤", "休闲裤", "灯芯绒", "短裤"]
}
process_templates = {
    "外套": ["Proc_A_裁剪", "Proc_B_缝纫"],
    "衬衫": ["Proc_A_裁剪", "Proc_B_缝纫", "Proc_C_整烫"],
    "裤子": ["Proc_A_裁剪", "Proc_B_缝纫"]
}
factories = [["F_CN_01"], ["F_TH_01"], ["F_CN_01", "F_TH_01"]]

# 日期范围
start_date = datetime(2025, 11, 1)
end_date = datetime(2026, 1, 1)

# 随机生成日期
def random_date():
    delta = (end_date - start_date).days
    return (start_date + timedelta(days=random.randint(0, delta))).strftime("%Y-%m-%d")

# 生成单个订单
def generate_order(i):
    product_type = random.choice(product_types)
    customer = random.choice(customers)
    prefix = random.choice(style_prefix[product_type])
    style_name = random.choice(style_names[product_type])
    style_code = f"{prefix}-{style_name}-{str(random.randint(1, 20)).zfill(3)}"
    quantity = random.randint(500, 10000)
    eligible = random.choice(factories)

    # 工序能力 = 订单量 × [1.1~1.5]，每个工序不同
    total_process_capacity = {}
    for proc in process_templates[product_type]:
        multiplier = random.uniform(1.1, 1.5)
        capacity = int(quantity * multiplier)
        total_process_capacity[proc] = capacity

    return {
        "order_id": f"ORD_{str(i+1).zfill(3)}",
        "customer": customer,
        "product_type": product_type,
        "style": style_code,
        "quantity": quantity,
        "due_date": random_date(),
        "material_purchasing_lead_time": random.randint(5, 30),
        "material_transportation_to_region_lead_time": {
            "CHINA": random.randint(20, 50),
            "THAILAND": random.randint(22, 60)
        },
        "production_lead_time": random.randint(2, 8),
        "total_process_capacity": total_process_capacity,
        "eligible_factories": eligible
    }

# 生成100条订单
test_data_orders = [generate_order(i) for i in range(100)]

# 保存为 JSON 文件
with open("data/test_data_orders.json", "w", encoding="utf-8") as f:
    json.dump(test_data_orders, f, ensure_ascii=False, indent=2)

# 示例打印前 3 条
print(json.dumps(test_data_orders[:3], ensure_ascii=False, indent=2))
