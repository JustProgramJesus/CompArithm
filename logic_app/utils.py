import random

# Конфигурация
MAX_LEVELS = 10
MAX_NODES_PER_LEVEL = 10
MAX_NUMBER = 7
MAX_BASE = 10
OP_SYMBOLS = {
    "OR": "∨", "AND": "∧", "XOR": "⊕", "EQUIV": "≡", "IMPLIES": "→",
    "NAND": "|", "NOR": "↓", "NOT_IMPLIES": "¬→", "NOT_X": "¬x", "X": "x",
    "Y": "y", "LEFT": "←", "NOT_LEFT": "¬←", "NOT_Y": "¬y"
}
OPERATIONS = [
    "OR", "AND", "XOR", "EQUIV", "IMPLIES", "NAND", "NOR",
    "NOT_IMPLIES", "NOT_X", "X", "Y", "LEFT", "NOT_LEFT", "NOT_Y"
]

OPERATION_INPUT_RULES = {
    0: (1, None), 1: (1, None), 2: (1, None), 3: (1, None),
    4: (1, None), 5: (1, None), 6: (1, None), 7: (1, None),
    8: (1, None), 9: (1, None), 10: (1, None), 11: (1, None),
    12: (1, None), 13: (1, None)
}



def int_to_base(n, base):
    digits = "0123456789"
    if n == 0:
        return "0"
    res = ""
    while n > 0:
        res = digits[n % base] + res
        n //= base
    return res


def apply_operation(op_code, inputs_bin):
    length = len(inputs_bin[0])
    result = []
    for i in range(length):
        try:
            bits = [int(x[i]) for x in inputs_bin]
        except IndexError:
            return '0' * length

        a = bits[0]
        b = bits[1] if len(bits) > 1 else a  # <--- вот ключ: если второго нет, используем a

        match OPERATIONS[op_code]:
            case "AND": res = int(a and b)
            case "OR": res = int(a or b)
            case "XOR": res = int((a and not b) or (not a and b))
            case "EQUIV": res = int(a == b)
            case "IMPLIES": res = int((not a) or b)
            case "NAND": res = int(not (a and b))
            case "NOR": res = int(not (a or b))
            case "NOT_IMPLIES": res = int(not ((not a) or b))
            case "NOT_X": res = int(not a)
            case "X": res = a
            case "Y": res = b
            case "LEFT": res = int((not b) or a)
            case "NOT_LEFT": res = int(not ((not b) or a))
            case "NOT_Y": res = int(not b)
            case _: res = 0
        result.append(str(res))
    return ''.join(result)



def generate_quasi_uniform_bases(count, min_base=2, max_base=10):
    bases = list(range(min_base, max_base + 1))
    result = []
    while len(result) < count:
        result.extend(bases)
    random.shuffle(result)
    return result[:count]


def generate_logic_graph():
    num_levels = random.randint(2, MAX_LEVELS)
    levels = []
    structure = tuple(random.randint(2, MAX_NODES_PER_LEVEL) for _ in range(num_levels))

    level0_count = structure[0]
    bases0 = generate_quasi_uniform_bases(level0_count, 2, MAX_BASE)
    current_level = []

    nums0 = list(range(0, MAX_NUMBER, max(1, MAX_NUMBER // level0_count)))
    while len(nums0) < level0_count:
        nums0.append(random.randint(0, MAX_NUMBER))
    random.shuffle(nums0)
    nums0 = nums0[:level0_count]

    for base, num in zip(bases0, nums0):
        val_in_base = int_to_base(num, base)
        val_in_bin = bin(num)[2:].zfill(3)
        current_level.append([base, val_in_base, val_in_bin])
    levels.append(current_level)

    for level_index in range(1, num_levels):
        level_node_count = structure[level_index]
        current_level = []
        prev_level = levels[level_index - 1]
        available_inputs = len(prev_level)

        for _ in range(level_node_count):
            valid_ops = [op for op in range(len(OPERATIONS)) if OPERATION_INPUT_RULES[op][0] <= available_inputs]
            if not valid_ops:
                op_code = 9
                min_inputs_rule, max_inputs_rule = 1, 1
            else:
                op_code = random.choice(valid_ops)
                min_inputs_rule, max_inputs_rule = OPERATION_INPUT_RULES[op_code]
            max_possible = available_inputs if max_inputs_rule is None else min(max_inputs_rule, available_inputs)
            input_count = random.randint(min_inputs_rule, max_possible)
            inputs = sorted(random.sample(range(available_inputs), input_count))
            node = [op_code] + inputs
            current_level.append(node)
        levels.append(current_level)

    for level_index in range(1, num_levels):
        prev_level = levels[level_index - 1]
        current_level = levels[level_index]
        out_bases = generate_quasi_uniform_bases(len(current_level), 2, MAX_BASE)

        for idx, operation in enumerate(current_level):
            op_code = operation[0]
            input_indices = operation[1:]
            inputs_bin = []
            for i in input_indices:
                if 0 <= i < len(prev_level):
                    node_bin = prev_level[i][-1]
                    if isinstance(node_bin, str):
                        inputs_bin.append(node_bin)
            result_bin = apply_operation(op_code, inputs_bin) if inputs_bin else '0' * 3
            res_int = int(result_bin, 2)
            out_base = out_bases[idx]
            result_in_base = int_to_base(res_int, out_base)
            operation.extend([out_base, result_in_base, result_bin])

    return tuple(levels)

from collections import defaultdict

def enrich_table_data_with_operations(table_data):
    enriched_by_level = defaultdict(list)
    levels = defaultdict(list)

    # Собираем данные по уровням
    for row in table_data:
        levels[row["level"]].append(row)

    for row in table_data:
        level = row["level"]

        if level == 0:
            # Для уровня 0 выводим только базовую информацию
            enriched_by_level[level].append({
                "level": level,
                "node": row["node"],
                "reference_result": f'{row["result"]}_{row["base"]}'
            })
        else:
            # Для остальных уровней формируем полную строку
            input_indices = row["inputs"] if isinstance(row["inputs"], list) else [int(i) for i in
                                                                                   str(row["inputs"]).replace(",",
                                                                                                              " ").split()
                                                                                   if i.strip().isdigit()]

            args = []
            for idx in input_indices:
                prev = next((r for r in levels[level - 1] if r["node"] == idx), None)
                if prev:
                    args.append(f'{prev["result"]}_{prev["base"]}')

            op_symbol = OP_SYMBOLS.get(row["operation"], row["operation"])
            operation_expr = f" {op_symbol} ".join(args)
            final_result = f'{row["result"]}_{row["base"]}'

            enriched_by_level[level].append({
                "level": level,
                "node": row["node"],
                "operation_expr": operation_expr,
                "reference_result": final_result,
                "verifier_result": final_result
            })

    return dict(enriched_by_level)

# def generate_protocol_simplified(levels):
#     lines = []
#     lines.append("ПРОТОКОЛ МОДЕЛИ")
#     lines.append("=" * 90)
#     now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     lines.append(f"Дата: {now}\n")
#
#     for level_idx, level in enumerate(levels):
#         lines.append(f"УРОВЕНЬ {level_idx}")
#         lines.append("-" * 90)
#         header = f"{'Операции и аргументы':<50} | {'Значение и СС':<30}"
#         lines.append(header)
#         lines.append("-" * 90)
#
#         for node in level:
#             if level_idx == 0:
#                 base, val_base, _ = node
#                 op_info = f"Вход: {val_base}"
#                 val_info = f"{val_base}_{base}"
#             else:
#                 op_code = node[0]
#                 inputs = node[1:-3]
#                 base = node[-3]
#                 val_base = node[-2]
#                 op_str = f"{op_code}({','.join(map(str, inputs))})"
#                 op_info = f"Операция {op_str}"
#                 val_info = f"{val_base}_{base}"
#             lines.append(f"{op_info:<50} | {val_info:<30}")
#
#         lines.append("=" * 90 + "\n")
#
#     return "\n".join(lines)