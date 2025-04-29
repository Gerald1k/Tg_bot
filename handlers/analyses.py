from aiogram import Router, F
from keyboards.main_menu import InlineKeyboardButton, InlineKeyboardMarkup, analysis_keyboard
from aiogram.types import(
    Message,
    FSInputFile,
    CallbackQuery
    )
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, delete, desc, func
from datetime import datetime, date, timedelta
import dateparser
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import re
import tempfile
from io import BytesIO
import os

from states.analysis_states import AddAnalysis, DeleteFlow
from db import async_session, AnalyzesMem, Analysis
router = Router() 


@router.message(F.text == "🧪 Анализы")
async def analyses_menu_handler(message: Message):
    await message.answer("Выберите действие с анализами:", reply_markup=analysis_keyboard)



@router.message(F.text == "➕ Добавить анализ")
async def start_add_analysis(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Введите дату сдачи анализов (дд.мм.гггг, 'сегодня', 'вчера'):"
    )
    await state.set_state(AddAnalysis.date)


@router.message(AddAnalysis.date)
async def process_date(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    try:
        if text in ['сегодня', 'today']:
            parsed_date = date.today()
        elif text in ['вчера', 'yesterday']:
            parsed_date = date.today() - timedelta(days=1)
        else:
            dt = dateparser.parse(text, languages=['ru', 'en'])
            if not dt:
                raise ValueError
            parsed_date = dt.date()

        await state.update_data(date=parsed_date)

        async with async_session() as session:
            q = select(AnalyzesMem.group_name).distinct()
            res = await session.execute(q)
            groups = [r[0] for r in res.all()]

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=g, callback_data=f"group|{g}")] for g in groups
            ] + [[InlineKeyboardButton(text="✅ Закончить ввод", callback_data="finish")]]
        )
        await message.answer("Выберите группу анализа:", reply_markup=kb)
        await state.set_state(AddAnalysis.select_group)
    except Exception:
        await message.answer(
            "❌ Не удалось распознать дату. Введите в формате дд.мм.гггг, 'сегодня' или 'вчера'."
        )


@router.callback_query(F.data.startswith('group|'), AddAnalysis.select_group)
async def choose_group(callback: CallbackQuery, state: FSMContext):
    group = callback.data.split("|", 1)[1]
    await state.update_data(group=group)

    async with async_session() as session:
        q = select(AnalyzesMem.name).where(AnalyzesMem.group_name == group).distinct()
        res = await session.execute(q)
        names = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=n, callback_data=f"analysis|{n}")] for n in names
        ] + [[InlineKeyboardButton(text="🔙 Назад к группам", callback_data="back_to_groups")]]
    )
    await callback.message.answer(f"Группа: {group}. Выберите анализ:", reply_markup=kb)
    await state.set_state(AddAnalysis.select_analysis)
    await callback.answer()


@router.callback_query(F.data == 'back_to_groups', AddAnalysis.select_analysis)
async def back_to_groups(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        q = select(AnalyzesMem.group_name).distinct()
        res = await session.execute(q)
        groups = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=g, callback_data=f"group|{g}")] for g in groups
        ] + [[InlineKeyboardButton(text="✅ Закончить ввод", callback_data="finish")]]
    )
    await callback.message.answer("Выберите группу анализа:", reply_markup=kb)
    await state.set_state(AddAnalysis.select_group)
    await callback.answer()


@router.callback_query(F.data.startswith('analysis|'), AddAnalysis.select_analysis)
async def choose_analysis(callback: CallbackQuery, state: FSMContext):
    name = callback.data.split("|", 1)[1]
    data = await state.get_data()
    group = data.get("group")

    async with async_session() as session:
        q = select(AnalyzesMem).where(
            AnalyzesMem.group_name == group,
            AnalyzesMem.name == name
        )
        res = await session.execute(q)
        variants = res.scalars().all()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{v.unit} ({v.reference_values})", callback_data=f"variant|{v.id}")] for v in variants
        ] + [[InlineKeyboardButton(text="🔙 Назад к анализам", callback_data="back_to_analyses")]]
    )
    await callback.message.answer(f"Анализ: {name}. Выберите Единицы измерения:", reply_markup=kb)
    await state.set_state(AddAnalysis.select_variant)
    await callback.answer()


@router.callback_query(F.data == 'back_to_analyses', AddAnalysis.select_variant)
async def back_to_analyses(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    group = data.get("group")

    async with async_session() as session:
        q = select(AnalyzesMem.name).where(AnalyzesMem.group_name == group).distinct()
        res = await session.execute(q)
        names = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=n, callback_data=f"analysis|{n}")] for n in names
        ] + [[InlineKeyboardButton(text="🔙 Назад к группам", callback_data="back_to_groups")]]
    )
    await callback.message.answer(f"Группа: {group}. Выберите анализ:", reply_markup=kb)
    await state.set_state(AddAnalysis.select_analysis)
    await callback.answer()


@router.callback_query(F.data.startswith('variant|'), AddAnalysis.select_variant)
async def choose_variant(callback: CallbackQuery, state: FSMContext):
    mem_id = int(callback.data.split("|", 1)[1])
    async with async_session() as session:
        mem = await session.get(AnalyzesMem, mem_id)

    # Сохраняем в state все, что нужно для пересчёта и сохранения
    await state.update_data(
        mem_id=mem_id,
        name=mem.name,
        # коэффициент пересчёта в стандартную единицу
        conversion_to_standard=mem.conversion_to_standard,
        # стандартная единица и её референсные значения
        standard_unit=mem.standard_unit,
        standard_reference=mem.standard_reference
    )

    await callback.message.answer(
        f"Вы выбрали: {mem.name} — {mem.unit} ({mem.reference_values}).\nВведите результат анализа(например 5.6):"
    )
    await state.set_state(AddAnalysis.result)
    await callback.answer()


@router.message(AddAnalysis.result)
async def process_result(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        raw_val = float(message.text.strip())

        # Пересчитываем в стандартные единицы и округляем до сотых
        standardized_val = round(raw_val * data['conversion_to_standard'], 2)

        async with async_session() as session:
            async with session.begin():
                new = Analysis(
                    telegram_id=message.from_user.id,
                    name=data['name'],
                    group_name=data['group'],
                    units=data['standard_unit'],
                    reference=data['standard_reference'],
                    result=str(standardized_val),
                    date=data['date']
                )
                session.add(new)

        # После сохранения — показать клавиатуру выбора
        async with async_session() as session:
            q = select(AnalyzesMem.group_name).distinct()
            res = await session.execute(q)
            groups = [r[0] for r in res.all()]

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=g, callback_data=f"group|{g}")]
                for g in groups
            ] + [[InlineKeyboardButton(text="✅ Закончить ввод", callback_data="finish")]]
        )
        await message.answer(
            f"✅ Сохранено: {data['name']} = {standardized_val} {data['standard_unit']}.\n"
            "Выберите следующий анализ или закончите:",
            reply_markup=kb
        )
        await state.set_state(AddAnalysis.select_group)

    except ValueError:
        await message.answer("❌ Неверный формат числа. Введите результат ещё раз.")

@router.callback_query(F.data == "finish", AddAnalysis.select_group)
async def finish_adding(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Ввод анализов завершён.", reply_markup=analysis_keyboard)
    await state.clear()
    await callback.answer()

# --------------- Просмотр анализов -----------------

pdfmetrics.registerFont(
    TTFont('ArialUnicode', r'C:\Windows\Fonts\arial.ttf')
)

@router.message(F.text == "📋 Посмотреть анализы")
async def show_analysis_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Все анализы", callback_data="view_option|all")],
        [InlineKeyboardButton(text="По дате сдачи", callback_data="view_option|date")],
        [InlineKeyboardButton(text="Динамика", callback_data="view_option|trend")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_view")]
    ])
    await message.answer("Выберите опцию отображения анализов:", reply_markup=kb)

# 2. Обработка выбора опции
@router.callback_query(F.data.startswith("view_option|"))
async def handle_view_option(callback: CallbackQuery):
    option = callback.data.split("|", 1)[1]
    # Опция "Все анализы"
    if option == "all":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Сообщением", callback_data="all_msg")],
            [InlineKeyboardButton(text="PDF", callback_data="all_pdf")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="show_menu")]
        ])
        await callback.message.answer("Как вы хотите получить все анализы?", reply_markup=kb)

    # Опция "По дате сдачи"
    elif option == "date":
        async with async_session() as session:
            q = select(Analysis.date).where(
                Analysis.telegram_id == callback.from_user.id
            ).distinct().order_by(desc(Analysis.date))
            res = await session.execute(q)
            dates = [r[0] for r in res.all()]
        if not dates:
            await callback.message.answer("У вас нет ни одного анализа.")
        else:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=d.strftime("%d.%m.%Y"), callback_data=f"view_date|{d.isoformat()}")]
                    for d in dates
                ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="show_menu")]]
            )
            await callback.message.answer("Выберите дату сдачи:", reply_markup=kb)

    # Опция "Динамика"
    elif option == "trend":
        # Выводим группы анализов, как в текущей реализации
        async with async_session() as session:
            q = select(Analysis.group_name).where(
                Analysis.telegram_id == callback.from_user.id
            ).distinct()
            res = await session.execute(q)
            groups = [r[0] for r in res.all()]
        if not groups:
            await callback.message.answer("📋 У вас ещё нет ни одного анализа.")
        else:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=g, callback_data=f"view_group|{g}")]
                    for g in groups
                ] + [[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_view")]]
            )
            await callback.message.answer(
                "Выберите группу анализов для просмотра:", reply_markup=kb
            )
    await callback.answer()

# 3. Вывод всех анализов сообщением (последние результаты)
@router.callback_query(F.data == "all_msg")
async def all_msg(callback: CallbackQuery):
    async with async_session() as session:
        subq = select(
            Analysis.name,
            func.max(Analysis.date).label("max_date")
        ).where(
            Analysis.telegram_id == callback.from_user.id
        ).group_by(Analysis.name).subquery()
        q = select(
            Analysis.name,
            Analysis.result,
            Analysis.reference,
            Analysis.date
        ).join(
            subq,
            (Analysis.name == subq.c.name) & (Analysis.date == subq.c.max_date)
        )
        res = await session.execute(q)
        rows = res.all()

    if not rows:
        await callback.message.answer("У вас нет ни одного анализа.")
        await callback.answer()
        return

    text = "<b>Последние результаты по всем анализам:</b>\n"
    for name, result, reference, date in rows:
        # приводим к числу (учёт 4,5 и 4.5)
        res_num = None
        if result:
            try:
                res_num = float(result.replace(',', '.'))
            except ValueError:
                pass

        # парсим диапазон reference
        min_ref = max_ref = None
        if reference:
            parts = re.split(r'[^0-9\.]+', reference)
            nums = [p.replace(',', '.') for p in parts if p]
            if len(nums) >= 2:
                try:
                    min_ref, max_ref = float(nums[0]), float(nums[1])
                except ValueError:
                    pass

        # выбираем эмодзи
        if res_num is not None and min_ref is not None and max_ref is not None:
            emoji = '🟢' if min_ref <= res_num <= max_ref else '🔴'
        else:
            emoji = ''

        text += f"{emoji}{name} = {result} ({date.strftime('%d.%m.%Y')})\n"

    await callback.message.answer(text)
    await callback.answer()

# 4. Вывод всех анализов в PDF (два последних результата)
@router.callback_query(F.data == "all_pdf")
async def all_pdf(callback: CallbackQuery):
    # --- Получаем данные ---
    async with async_session() as session:
        q = (
            select(Analysis)
            .where(Analysis.telegram_id == callback.from_user.id)
            .order_by(Analysis.name, desc(Analysis.date))
        )
        res = await session.execute(q)
        analyses = res.scalars().all()

    # --- Группируем по названию ---
    grouped = {}
    for a in analyses:
        grouped.setdefault(a.name, []).append(a)

    # --- Подготовка таблицы и стилей ---
    data = [[
        'Анализ', 'Последний результат (дата)',
        'Предыдущий результат (дата)', 'Референс', 'Ед. изм.'
    ]]
    styles = [
        ('FONTNAME',   (0,0), (-1,-1), 'ArialUnicode'),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
    ]

    # Шаблон для Paragraph
    stylesheet = getSampleStyleSheet()
    body = stylesheet['BodyText']
    body.fontName = 'ArialUnicode'
    body.fontSize = 10

    row = 1
    for name, items in grouped.items():
        last = items[0]
        prev = items[1] if len(items) > 1 else None

        # Функция для создания окрашенного Paragraph
        def make_para(item):
            txt = item.result
            date_str = item.date.strftime('%d.%m.%Y')
            color = None
            try:
                val = float(item.result.replace(',', '.'))
                parts = re.split(r'[^0-9,\.]+', item.reference or '')
                nums = [p.replace(',', '.') for p in parts if p]
                if len(nums) >= 2:
                    lo, hi = map(float, nums[:2])
                    color = 'green' if lo <= val <= hi else 'red'
            except:
                pass

            if color:
                # цветим только число, дату оставляем чёрной
                return Paragraph(
                    f'<font name="ArialUnicode">'
                    f'<font color="{color}">{txt}</font> '
                    f'({date_str})'
                    f'</font>',
                    body
                )
            else:
                return Paragraph(f'{txt} ({date_str})', body)

        last_para = make_para(last)
        prev_para = make_para(prev) if prev else Paragraph('—', body)

        data.append([
            Paragraph(name, body),
            last_para,
            prev_para,
            Paragraph(last.reference or '—', body),
            Paragraph(last.units or '—', body),
        ])
        row += 1

    # --- Генерируем PDF ---
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    tbl = Table(
        data,
        colWidths=[80, 150, 150, 70, 60],  # 80 пунктов для столбца "Ед. изм."
        repeatRows=1
    )
    tbl.setStyle(TableStyle(styles))
    doc.build([tbl])
    buf.seek(0)

    # --- Отправляем пользователю ---
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tf:
        tf.write(buf.read())
        path = tf.name

    await callback.message.answer_document(FSInputFile(path, filename='all_analyses.pdf'))
    await callback.answer()
    os.remove(path)

# 5. Вывод по дате
@router.callback_query(F.data.startswith("view_date|"))
async def view_date(callback: CallbackQuery):
    iso = callback.data.split("|", 1)[1]
    date = datetime.fromisoformat(iso).date()
    async with async_session() as session:
        q = select(Analysis.name, Analysis.result, Analysis.reference).where(
            Analysis.telegram_id == callback.from_user.id,
            Analysis.date == date
        )
        res = await session.execute(q)
        rows = res.all()

    if not rows:
        await callback.message.answer("Нет записей за выбранную дату.")
    else:
        text = f"<b>Результаты анализов за {date.strftime('%d.%m.%Y')}:</b>\n"
        for name, result, reference in rows:
            # пытаемся привести результат к числу (учёт 4,5 и 4.5)
            res_num = None
            if result:
                try:
                    res_num = float(result.replace(',', '.'))
                except ValueError:
                    pass

            # парсим границы референсного диапазона
            min_ref = max_ref = None
            if reference:
                parts = re.split(r'[^0-9,\.]+', reference)
                nums = [p.replace(',', '.') for p in parts if p]
                if len(nums) >= 2:
                    try:
                        min_ref, max_ref = float(nums[0]), float(nums[1])
                    except ValueError:
                        pass

            # выбираем эмодзи
            if res_num is not None and min_ref is not None and max_ref is not None:
                emoji = '🟢' if min_ref <= res_num <= max_ref else '🔴'
            else:
                emoji = ''

            text += f"{name} = {emoji}{result} ({reference})\n"
        await callback.message.answer(text)
        await callback.answer()

# 6. Группы и отдельный анализ (динамика) — текущая реализация
@router.callback_query(F.data.startswith("view_group|"))
async def view_group(callback: CallbackQuery):
    group = callback.data.split("|", 1)[1]
    async with async_session() as session:
        q = select(Analysis.name).where(
            Analysis.telegram_id == callback.from_user.id,
            Analysis.group_name == group
        ).distinct()
        res = await session.execute(q)
        names = [r[0] for r in res.all()]

    if not names:
        await callback.message.answer(
            "В выбранной группе у вас ещё нет ни одного анализа.",
            reply_markup=None
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=n, callback_data=f"view_analysis|{n}")]
                for n in names
            ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="cancel_view")]]
        )
        await callback.message.answer(
            f"Группа: {group}. Выберите анализ:",
            reply_markup=kb
        )
    await callback.answer()

@router.callback_query(F.data.startswith("view_analysis|"))
async def view_analysis(callback: CallbackQuery):
    name = callback.data.split("|", 1)[1]
    async with async_session() as session:
        q = select(Analysis).where(
            Analysis.telegram_id == callback.from_user.id,
            Analysis.name == name
        ).order_by(desc(Analysis.date))
        res = await session.execute(q)
        analyses = res.scalars().all()

    if not analyses:
        await callback.message.answer(
            "У вас нет записей для этого анализа."
        )
    else:
        text = f"<b>Анализы {name}:</b>\n\n"
        for a in analyses:
            dt = a.date.strftime("%d.%m.%Y") if a.date else '—'
            res_num = None
            if a.result:
                try:
                    res_num = float(a.result.replace(',', '.'))
                except ValueError:
                    pass

            # парсим границы нормы из строки reference, например "60-80"
            min_ref = max_ref = None
            if a.reference:
                parts = re.split(r'[^0-9,\.]+', a.reference)
                nums = [p.replace(',', '.') for p in parts if p]
                if len(nums) >= 2:
                    try:
                        min_ref, max_ref = float(nums[0]), float(nums[1])
                    except ValueError:
                        pass

            # выбираем эмодзи: 🟢 если в норме, 🔴 если вне
            if res_num is not None and min_ref is not None and max_ref is not None:
                emoji = '🟢' if min_ref <= res_num <= max_ref else '🔴'
            else:
                emoji = ''

            text += (
                f"📅 {dt}: {emoji}{a.result or '—'} {a.units or ''} "
                f"(Референс: {a.reference or '—'})\n"
            )
        await callback.message.answer(text)
    await callback.answer()

# 7. Отмена просмотра
@router.callback_query(F.data == "cancel_view" or F.data == "show_menu")
async def cancel_view(callback: CallbackQuery):
    await callback.message.answer("Просмотр анализов отменён.")
    await callback.answer()
    
# --------------- Удаление анализов -----------------
@router.message(F.text == "❌ Удалить анализ")
async def start_delete_analysis(message: Message, state: FSMContext):
    # Шаг 1: список групп
    async with async_session() as session:
        res = await session.execute(
            select(Analysis.group_name)
            .where(Analysis.telegram_id == message.from_user.id)
            .distinct()
        )
        groups = [r[0] for r in res.all()]

    if not groups:
        await message.answer("У вас ещё нет ни одного анализа для удаления.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=g, callback_data=f"del_group|{g}")]
            for g in groups
        ] + [[InlineKeyboardButton(text="❌ Отмена", callback_data="del_cancel")]]
    )
    await message.answer("Выберите группу анализа для удаления:", reply_markup=kb)
    await state.set_state(DeleteFlow.waiting_for_group)

# Отмена на первом шаге — выход из потока
@router.callback_query(DeleteFlow.waiting_for_group, F.data == "del_cancel")
async def cancel_delete_group(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Удаление отменено.")
    await state.clear()
    await callback.answer()

@router.callback_query(DeleteFlow.waiting_for_group, F.data.startswith("del_group|"))
async def choose_delete_group(callback: CallbackQuery, state: FSMContext):
    group = callback.data.split("|", 1)[1]
    await state.update_data(group=group)

    # Шаг 2: список названий в группе
    async with async_session() as session:
        res = await session.execute(
            select(Analysis.name)
            .where(
                Analysis.telegram_id == callback.from_user.id,
                Analysis.group_name == group
            )
            .distinct()
        )
        names = [r[0] for r in res.all()]

    if not names:
        await callback.message.edit_text("В этой группе нет анализов.")
        await state.clear()
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=n, callback_data=f"del_name|{n}")]
            for n in names
        ] + [[InlineKeyboardButton(text="◀️ Назад", callback_data="del_back")]]
    )
    await callback.message.edit_text("Выберите название анализа:", reply_markup=kb)
    await state.set_state(DeleteFlow.waiting_for_name)
    await callback.answer()

# «Назад» к выбору группы
@router.callback_query(DeleteFlow.waiting_for_name, F.data == "del_back")
async def back_to_group(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        res = await session.execute(
            select(Analysis.group_name)
            .where(Analysis.telegram_id == callback.from_user.id)
            .distinct()
        )
        groups = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=g, callback_data=f"del_group|{g}")]
            for g in groups
        ] + [[InlineKeyboardButton(text="❌ Отмена", callback_data="del_cancel")]]
    )
    await callback.message.edit_text("Выберите группу анализа для удаления:", reply_markup=kb)
    await state.set_state(DeleteFlow.waiting_for_group)
    await callback.answer()

@router.callback_query(DeleteFlow.waiting_for_name, F.data.startswith("del_name|"))
async def choose_delete_name(callback: CallbackQuery, state: FSMContext):
    name = callback.data.split("|", 1)[1]
    await state.update_data(name=name)

    # Шаг 3: список конкретных записей
    async with async_session() as session:
        res = await session.execute(
            select(Analysis)
            .where(
                Analysis.telegram_id == callback.from_user.id,
                Analysis.name == name
            )
            .order_by(desc(Analysis.date))
        )
        analyses = res.scalars().all()

    if not analyses:
        await callback.message.edit_text("Нет записей для этого анализа.")
        await state.clear()
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{a.date.strftime('%d.%m.%Y')}: {a.result or '—'} {a.units or ''}",
                callback_data=f"del_select|{a.id}"
            )]
            for a in analyses
        ] + [[InlineKeyboardButton(text="◀️ Назад", callback_data="del_back")]]
    )
    await callback.message.edit_text(
        f"Вы выбрали «{name}». Выберите запись для удаления:",
        reply_markup=kb
    )
    await state.set_state(DeleteFlow.waiting_for_analysis)
    await callback.answer()

# «Назад» к выбору названия анализа
@router.callback_query(DeleteFlow.waiting_for_analysis, F.data == "del_back")
async def back_to_name(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    group = data.get("group")
    async with async_session() as session:
        res = await session.execute(
            select(Analysis.name)
            .where(
                Analysis.telegram_id == callback.from_user.id,
                Analysis.group_name == group
            )
            .distinct()
        )
        names = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=n, callback_data=f"del_name|{n}")]
            for n in names
        ] + [[InlineKeyboardButton(text="◀️ Назад", callback_data="del_back")]]
    )
    await callback.message.edit_text("Выберите название анализа:", reply_markup=kb)
    await state.set_state(DeleteFlow.waiting_for_name)
    await callback.answer()

@router.callback_query(DeleteFlow.waiting_for_analysis, F.data.startswith("del_select|"))
async def confirm_delete(callback: CallbackQuery, state: FSMContext):
    analysis_id = int(callback.data.split("|", 1)[1])
    async with async_session() as session:
        analysis = await session.get(Analysis, analysis_id)

    if not analysis:
        await callback.message.edit_text("Запись не найдена.")
        await state.clear()
        return

    await state.update_data(analysis_id=analysis_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[  
            InlineKeyboardButton(text="✅ Да", callback_data=f"del_confirm|{analysis_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="del_cancel")
        ]]
    )
    await callback.message.edit_text(
        f"Удалить анализ «{analysis.name}» от {analysis.date.strftime('%d.%m.%Y')}?",
        reply_markup=kb
    )
    await state.set_state(DeleteFlow.confirm_delete)
    await callback.answer()

@router.callback_query(DeleteFlow.confirm_delete, F.data.startswith("del_confirm|"))
async def process_delete_confirm(callback: CallbackQuery, state: FSMContext):
    analysis_id = int(callback.data.split("|", 1)[1])
    async with async_session() as session:
        async with session.begin():
            await session.execute(delete(Analysis).where(Analysis.id == analysis_id))

    await callback.message.edit_text("✅ Анализ успешно удалён.")
    await state.clear()
    await callback.answer()