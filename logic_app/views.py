import itertools

from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.http import urlencode
import json
from .utils import generate_logic_graph, OPERATIONS, enrich_table_data_with_operations
from django.template.defaulttags import register
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse, FileResponse
import os
from datetime import datetime


# generate_protocol_simplified
@register.filter
def groupby(value, arg):
    return itertools.groupby(value, lambda x: x[arg])


OP_SYMBOLS = {
    "OR": "∨", "AND": "∧", "XOR": "⊕", "EQUIV": "≡", "IMPLIES": "→",
    "NAND": "|", "NOR": "↓", "NOT_IMPLIES": "¬→", "NOT_X": "¬x", "X": "x",
    "Y": "y", "LEFT": "←", "NOT_LEFT": "¬←", "NOT_Y": "¬y"
}


@csrf_exempt
def save_attempt_log(request):
    if request.method == "POST":
        import json
        data = json.loads(request.body)
        log_text = data.get("log", "")
        filename = "attempt_log.txt"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(log_text + "\n" + "=" * 80 + "\n")
        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "Invalid method"}, status=405)


# Выдача протокола модели
def download_protocol(request):
    path = "attempt_log.txt"
    if not os.path.exists(path):
        return HttpResponse("Файл не найден", status=404)

    with open(path, "rb") as f:
        response = HttpResponse(f.read(), content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="protocol.txt"'
        return response


def graph_view(request):
    # Получаем данные из GET-параметров
    fio = request.GET.get("fio", "")
    run_number = request.GET.get("run", "")
    attempts_left = int(request.GET.get("attempts", 3))
    # Десериализуем данные из JSON строк
    elements_json = request.GET.get("elements", "[]")
    level_labels_json = request.GET.get("level_labels", "[]")
    table_data_json = request.GET.get("table_data", "[]")
    try:
        elements = json.loads(elements_json)
        level_labels = json.loads(level_labels_json)
        table_data = json.loads(table_data_json)
    except json.JSONDecodeError:
        elements = []
        level_labels = []
        table_data = []
    enriched_table = enrich_table_data_with_operations(table_data)
    print("Enriched Table:", enriched_table)
    max_level = int(request.GET.get("max_level", 0))
    max_level_nodes = sum(1 for row in table_data if row["level"] == max_level)
    pattern = build_pattern(max_level_nodes)
    return render(request, "logic_app/graph.html", {
        "elements": elements,
        "level_labels": level_labels,
        "table_data": json.dumps(table_data),
        "fio": fio,
        "run_number": run_number,
        "max_level": max_level,
        "attempts_left": attempts_left,
        "enriched_rows": enriched_table,
        "enriched_table": enriched_table,
        "pattern": pattern,
        "max_level_nodes": max_level_nodes,  # Передаем количество узлов
    })


def start_view(request):
    if request.method == "POST":
        fio = request.POST.get("fio", "").strip()
        run_number = request.POST.get("run_number", "").strip()

        errors = {}
        if not fio.replace(" ", "").isalpha():
            errors["fio"] = "ФИО должно содержать только буквы и пробелы"
        if not run_number.isdigit() or int(run_number) < 1:
            errors["run_number"] = "Номер прогона должен быть положительным числом"

        if errors:
            return render(request, "logic_app/start.html", {"errors": errors})

        # Генерируем граф
        levels = generate_logic_graph()
        elements = []
        level_labels = []
        table_data = []

        for level_idx, level in enumerate(levels):
            level_y = level_idx * 200
            level_labels.append({
                "y": level_y,
                "top_adjusted": level_y + 30,
                "label": f"Уровень {level_idx}"
            })

            for node_idx, node in enumerate(level):
                node_id = f"Y{level_idx}_{node_idx}"
                x = node_idx * 200
                y = level_y

                if level_idx == 0:
                    base, val_base, bin_val = node
                    label = f"[{val_base}]"
                    data_label = f"[{val_base}]"
                    bin_label = f"[{bin_val}]₂"
                    op = "INPUT"
                    inputs = "-"
                else:
                    op_code = node[0]
                    inputs = node[1:-3]
                    base = node[-3]
                    val_base = node[-2]
                    bin_val = node[-1]
                    symbol = OP_SYMBOLS.get(OPERATIONS[op_code], OPERATIONS[op_code])
                    label = symbol
                    data_label = f"{val_base}_{base}"
                    bin_label = f"{bin_val}"
                    for src in inputs:
                        elements.append({
                            "data": {
                                "source": f"Y{level_idx - 1}_{src}",
                                "target": node_id
                            }
                        })

                elements.append({
                    "data": {
                        "id": node_id,
                        "label": label,
                        "dataLabel": data_label,
                        "binLabel": bin_label,
                        "base": base,
                        "inputs": inputs if not isinstance(inputs, str) else []
                    },
                    "position": {"x": x, "y": y}
                })

                table_data.append({
                    "level": level_idx,
                    "node": node_idx,
                    "operation": label,
                    "inputs": inputs if isinstance(inputs, str) else ", ".join(map(str, inputs)),
                    "base": base,
                    "result": val_base,
                    "bin": bin_val
                })
                enriched_table = enrich_table_data_with_operations(table_data)

        # Подготавливаем параметры для передачи
        params = {
            "fio": fio,
            "run": run_number,
            "elements": json.dumps(elements),
            "level_labels": json.dumps(level_labels),
            "table_data": json.dumps(table_data),
            "enriched_table": json.dumps(enriched_table),  # ← вот это добавлено
            "max_level": len(levels) - 1,
            "attempts": 3
        }

        # Кодируем параметры и перенаправляем
        encoded_params = urlencode(params)
        return redirect(f"{reverse('graph')}?{encoded_params}")

    return render(request, "logic_app/start.html")


def verification_view(request):
    fio = request.GET.get("fio", "")
    run_number = request.GET.get("run", "")
    attempts_left = int(request.GET.get("attempts", 3))
    max_level = request.GET.get("max_level", 0)

    try:
        elements = json.loads(request.GET.get("elements", "[]"))
        level_labels = json.loads(request.GET.get("level_labels", "[]"))
        table_data = json.loads(request.GET.get("table_data", "[]"))
        enriched_table = json.loads(request.GET.get("enriched_table", "{}"))
    except json.JSONDecodeError:
        elements = []
        level_labels = []
        table_data = []
        enriched_table = {}

    return render(request, "logic_app/verification.html", {
        "max_level": max_level,
        "elements": elements,
        "level_labels": level_labels,
        "table_data": table_data,
        "enriched_table": enriched_table,
        "enriched_rows": enriched_table,
    })



from django.shortcuts import render, redirect
from django.http import JsonResponse

def verify_view(request):
    if request.method == "POST":
        # Получаем данные из формы
        fio = request.POST.get("fio", "").strip()
        run_number = request.POST.get("run_number", "").strip()
        attempts_left = int(request.POST.get("attempts_left", 2))
        user_answers = request.POST.get("answers", "").replace(";", "").strip()
        # Получаем enriched_table (уже предполагалось строкой)
        enriched_table = request.POST.get("enriched_table", "")

        # Проверяем enriched_table
        if isinstance(enriched_table, str):
            try:
                # Можно организовать десериализацию через eval, но только если строго доверяем данным
                # Рекомендуется строго проверять формат перед этим!!!
                enriched_table = eval(enriched_table)  # Преобразование в Python объект
            except Exception as e:
                enriched_table = {}

        # Извлечение verifier_results уровнем
        verifier_results = []
        max_level = int(request.POST.get("max_level", 0))
        if isinstance(enriched_table, dict):
            verifier_results = [
                row.get("verifier_result", "").replace(";", "")
                for row in enriched_table.get(max_level, [])
            ]

        # Преобразуем правильный ответ в строку, чтобы совпадать с форматом пользовательского ввода
        correct_answer_string = " ".join(verifier_results)

        # Сравниваем ответы пользователя с эталонными
        is_correct = user_answers == correct_answer_string

        table_data = []
        if isinstance(enriched_table, dict):
            for level, rows in enriched_table.items():
                for row in rows:
                    table_data.append({
                        "level": level,
                        "node": row.get("node", ""),
                        "operation_expr": row.get("operation_expr", ""),
                        "reference_result": row.get("reference_result", ""),
                        "verifier_result": row.get("verifier_result", "")
                    })

        # Отправляем результат
        return render(request, "logic_app/result.html", {
            "fio": fio,
            "run_number": run_number,
            "attempts_left": attempts_left,
            "is_correct": is_correct,
            "comment": "Ответы совпадают!" if is_correct else "Ответы не совпадают.",
            "correct_answers": correct_answer_string,  # Отображаем корректный ответ как строку
            "enriched_table": enriched_table,  # Передаём enriched_table в шаблон
            "table_data": table_data  # Передаём таблицу данных для рендеринга
        })


def build_pattern(count):
    unit = r"\d+_\d+"
    return f"^{(' '.join([unit] * count))}$"


def get_report_content(request):
    if request.method == "GET":
        # Получаем данные для отчета
        fio = request.GET.get('fio', 'Неизвестный пользователь')
        run_number = request.GET.get('run_number', '1')
        attempt_number = request.GET.get('attempt_number', '1')
        user_answers = request.GET.get('user_answers', [])
        correct_answers = request.GET.get('correct_answers', [])
        comment = request.GET.get('comment', 'Нет комментария')

        # Формируем текст отчета
        report_text = f"""ОТЧЁТ О ПРОВЕРКЕ МОДЕЛИ
    ==================================================
    Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    Пользователь: {fio}
    Прогон №: {run_number}
    Попытка: {attempt_number}

    РЕЗУЛЬТАТЫ:
    - Ответ пользователя: {' '.join(user_answers)}
    - Правильный ответ: {' '.join(correct_answers)}

    КОММЕНТАРИЙ ПОЛЬЗОВАТЕЛЯ:
    {comment if comment.strip() else 'Нет комментария'}
    """
        return JsonResponse(
            {'content': report_text, 'filename': f'отчет_{fio}_прогон_{run_number}_попытка_{attempt_number}.txt'})


def get_protocol_content(request):
    if request.method == "GET":
        # Получаем данные графа из сессии
        graph_data = request.GET.get('graph_data', [])
        fio = request.GET.get('fio', 'Неизвестный пользователь')
        run_number = request.GET.get('run_number', '1')

        # Формируем текст протокола
        protocol_lines = [
            "ПРОТОКОЛ МОДЕЛИ",
            "=" * 50,
            f"Пользователь: {fio}",
            f"Прогон №: {run_number}",
            f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]

        for level_idx, level in enumerate(graph_data):
            protocol_lines.append(f"УРОВЕНЬ {level_idx}")
            protocol_lines.append("-" * 50)

            if level_idx == 0:
                protocol_lines.append("Значение y | Основание k")
                protocol_lines.append("-" * 25)
                for node in level:
                    protocol_lines.append(f"{node[1]} | {node[0]}")
            else:
                protocol_lines.append("Операция и аргументы | Результат (основание)")
                protocol_lines.append("-" * 50)

                for node in level:
                    op_code = node[0]
                    inputs = node[1:-3]
                    base = node[-3]
                    result = node[-2]
                    op_name = OPERATIONS[op_code] if op_code < len(OPERATIONS) else f"Операция {op_code}"

                    args = [f"{graph_data[level_idx - 1][i][1]}_{graph_data[level_idx - 1][i][0]}" for i in inputs]
                    operation_str = f"{op_name} ({', '.join(args)})"
                    result_str = f"{result}_{base}"

                    protocol_lines.append(f"{operation_str} | {result_str}")

            protocol_lines.append("=" * 50)
            protocol_lines.append("")

        protocol_text = "\n".join(protocol_lines)
        return JsonResponse({'content': protocol_text, 'filename': f'протокол_{fio}_прогон_{run_number}.txt'})