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
    run_number_save = request.GET.get("run", "")
    run_number = request.GET.get("run_number", "")
    attempts_left = int(request.GET.get("attempts", 3))
    # Десериализуем данные из JSON строк
    elements_json = request.GET.get("elements", "[]")
    level_labels_json = request.GET.get("level_labels", "[]")
    table_data_json = request.GET.get("table_data", "[]")
    score_counter = request.GET.get("score_counter", "0")
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
        "run": run_number_save,
        "run_number": run_number,
        "score_counter": score_counter,
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
        run_number = int(request.POST.get("run_number").strip())
        score_counter = request.POST.get("score_counter", "0")
        if run_number >= 3:
            run_number_save = run_number
            run_number = 3
        else:
            run_number_save = run_number

        errors = {}
        if not fio.replace(" ", "").isalpha():
            errors["fio"] = "ФИО должно содержать только буквы и пробелы"

        if errors:
            return render(request, "logic_app/start.html", {"errors": errors})

        # Генерируем граф
        levels = generate_logic_graph()
        if not levels or not any(levels):
            return render(request, "logic_app/start.html", {"message": "Ошибка генерации графа. Попробуйте ещё раз."})
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
            "run": run_number_save,
            "run_number": run_number,
            "elements": json.dumps(elements),
            "score_counter": score_counter,
            "level_labels": json.dumps(level_labels),
            "table_data": json.dumps(table_data),
            "enriched_table": json.dumps(enriched_table),
            "max_level": len(levels) - 1,
            "attempts": 3 - run_number
        }

        # Кодируем параметры и перенаправляем
        encoded_params = urlencode(params)
        return redirect(f"{reverse('graph')}?{encoded_params}")

    return render(request, "logic_app/start.html")

def verify_view(request):
    if request.method == "POST":
        # Получаем данные из формы
        fio = request.POST.get("fio", "").strip()
        run_number = request.POST.get("run_number", "").strip()
        attempts_left = int(request.POST.get("attempts_left", 2))
        user_answers = request.POST.get("answers", "").replace(";", "").strip()
        # Получаем enriched_table (уже предполагалось строкой)
        enriched_table = request.POST.get("enriched_table", "")
        run_number_save = request.POST.get("run", "")
        comment_user = request.POST.get("comment", "")

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
        score_counter = int(request.POST.get("score_counter", 0))
        is_correct = user_answers == correct_answer_string
        score_counter += int(is_correct)

        final_score = None
        if int(run_number) >= 3:
            final_score = 1 if score_counter > 0 else 0

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
            "run": run_number_save,
            "run_number": run_number,
            "attempts_left": attempts_left,
            "score_counter": score_counter,
            "final_score": final_score,
            "is_correct": is_correct,
            "comment": "Ответы совпадают!" if is_correct else "Ответы не совпадают.",
            "comment_user": comment_user,
            "correct_answers": correct_answer_string,  # Отображаем корректный ответ как строку
            "enriched_table": enriched_table,  # Передаём enriched_table в шаблон
            "table_data": table_data  # Передаём таблицу данных для рендеринга
        })


def build_pattern(count):
    unit = r"\d+_\d+"
    return f"^{(' '.join([unit] * count))}$"


def get_report_content(request):
    if request.method == "GET":
        fio = request.GET.get('fio', 'Неизвестный пользователь')
        run_number = request.GET.get('run_number', '1')
        attempt_number = request.GET.get('attempt_number', '1')
        user_answers = json.loads(request.GET.get('user_answers', '[]'))
        correct_answers = json.loads(request.GET.get('correct_answers', '[]'))
        comment = request.GET.get('comment', '').strip()
        date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        is_correct = request.GET.get('is_correct', 'false') == 'true'

        # Сборка строк отчета
        lines = [
            "ОТЧЁТ О ПРОВЕРКЕ МОДЕЛИ",
            "=" * 50,
            f"Дата: {date_str}   |   Пользователь: {fio}   |   Попытка: {attempt_number}",
            "",
            " " * 35 + "РЕЗУЛЬТАТЫ:",
            "- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -",
            "|  Номер   |    Ответ пользователя:     |       Правильный ответ:     |"
        ]

        for idx, (ua, ca) in enumerate(zip(user_answers, correct_answers), 1):
            lines.append(f"|    {str(idx).ljust(4)}  |  {ua.center(25)} |   {ca.center(25)} |")

        lines += [
            "- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -",
            "",
            "КОММЕНТАРИЙ ПОЛЬЗОВАТЕЛЯ:",
            comment if comment else "Нет комментария",
            "",
            "ИТОГ:",
            "Ваш ответ:"
            " ПРАВИЛЬНЫЙ ✅" if is_correct else "Ваш ответ:"
                                               " НЕПРАВИЛЬНЫЙ ❌"
        ]

        content = "\n".join(lines)
        filename = f"отчет_{fio}_прогон_{run_number}_попытка_{attempt_number}.txt"

        return JsonResponse({'content': content, 'filename': filename})

@csrf_exempt
def get_protocol_content(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            enriched_table = data.get("enriched_table", {})
            fio = data.get("fio", "Неизвестный пользователь")
            run_number = data.get("run_number", "1")

            # Определим последний уровень — исключим его
            level_keys = sorted([int(k) for k in enriched_table.keys()])
            max_level = max(level_keys)

            lines = [
                "ПРОТОКОЛ МОДЕЛИ",
                "=" * 50
            ]
            WIDTH_LEVEL = 8
            WIDTH_NODE = 12
            WIDTH_RESULT = 20
            WIDTH_OP = 25
            for level_num in level_keys:

                rows = enriched_table[str(level_num)]
                lines.append(f"УРОВЕНЬ {level_num}:")

                if level_num == 0:
                    lines.append(
                        f"| {'Уровень'.ljust(WIDTH_LEVEL)} | {'Индекс узла'.ljust(WIDTH_NODE)} | {'Результат'.ljust(WIDTH_RESULT)} |")
                    for row in rows:
                        lines.append(
                            f"| {str(row['level']).ljust(WIDTH_LEVEL)} | {str(row['node']).ljust(WIDTH_NODE)} | {str(row['reference_result']).ljust(WIDTH_RESULT)} |"
                        )
                else:
                    lines.append(
                        f"| {'Уровень'.ljust(WIDTH_LEVEL)} | {'Индекс узла'.ljust(WIDTH_NODE)} | {'Операция'.ljust(WIDTH_OP)} | {'Результат (эталон)'.ljust(WIDTH_RESULT)} |")
                    for row in rows:
                        operation = row.get("operation_expr", "").replace("\n", " ")[:WIDTH_OP]
                        lines.append(
                            f"| {str(row['level']).ljust(WIDTH_LEVEL)} | {str(row['node']).ljust(WIDTH_NODE)} | {operation.ljust(WIDTH_OP)} | {str(row['reference_result']).ljust(WIDTH_RESULT)} |"
                        )

                lines.append("")

            lines.append("=" * 50)
            lines.append(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Пользователь: {fio}")
            lines.append(f"Прогон №: {run_number}")

            content = "\n".join(lines)
            filename = f"протокол_{fio}_прогон_{run_number}.txt"
            return JsonResponse({'content': content, 'filename': filename})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
