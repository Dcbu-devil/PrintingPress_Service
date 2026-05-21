def calculate_commission(printing_cost: float, has_parent: bool, has_grandparent: bool):
    total_direct_commission = printing_cost * 0.10

    parent_commission = total_direct_commission * 0.05 if has_parent else 0
    grandparent_commission = total_direct_commission * 0.025 if has_grandparent else 0

    final_direct_agent_commission = (
        total_direct_commission
        - parent_commission
        - grandparent_commission
    )

    return {
        "total_direct_commission": round(total_direct_commission, 2),
        "parent_commission": round(parent_commission, 2),
        "grandparent_commission": round(grandparent_commission, 2),
        "final_direct_agent_commission": round(final_direct_agent_commission, 2),
    }