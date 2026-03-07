"""
Приложение «Обувной магазин» — демо-экзамен.
Работает напрямую с PostgreSQL (БД demoex: user_import, tovar, zakaz_import, punkty_vydachi_import).
"""
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk, filedialog

import psycopg2
from psycopg2.extras import RealDictCursor
from PIL import Image, ImageTk

from db_config import DB_CONFIG

ASSETS_DIR = Path(__file__).with_name("assets")
IMAGES_DIR = ASSETS_DIR / "images"
PLACEHOLDER_IMAGE = ASSETS_DIR / "picture.png"
ICON_ICO = ASSETS_DIR / "Icon.ico"
ICON_PNG = ASSETS_DIR / "Icon.png"

BACKGROUND_MAIN = "#FFFFFF"
BACKGROUND_SECONDARY = "#7FFF00"
ACCENT_COLOR = "#00FA9A"
DISCOUNT_BACKGROUND = "#2E8B57"
OUT_OF_STOCK_BACKGROUND = "#87CEFA"


class User:
    """Класс для хранения информации о пользователе системы."""

    def __init__(self, user_id, login, full_name, role):
        self.id = user_id
        self.login = login
        self.full_name = full_name
        self.role = role


class Database:
    """Класс работы с базой данных PostgreSQL (demoex)."""

    def __init__(self) -> None:
        """Открывает соединение с базой данных."""
        self.connection = psycopg2.connect(**DB_CONFIG)

    def get_user(self, login: str, password: str) -> User | None:
        """Возвращает пользователя по логину и паролю или None, если не найден."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT role_sotrudnika, fio, login
                FROM user_import
                WHERE login = %s AND password = %s
                """,
                (login, password),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return User(
            0,
            row["login"],
            row["fio"] or row["login"],
            row["role_sotrudnika"] or "Клиент",
        )

    def get_products(self) -> list[dict]:
        """Возвращает список всех товаров из таблицы tovar."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT articul, name_tovara, category_tovara, description, proizvoditel, postavschik,
                          cost, COALESCE(skidka, 0) AS skidka, ed_izmereniya, COALESCE(kolvo_na_sklade, 0) AS kolvo_na_sklade, photo
                   FROM tovar ORDER BY articul"""
            )
            rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r["articul"],
                "article": r["articul"],
                "name": r["name_tovara"] or "",
                "category": r["category_tovara"] or "",
                "description": r["description"] or "",
                "manufacturer": r["proizvoditel"] or "",
                "supplier": r["postavschik"] or "",
                "price": float(r["cost"] or 0),
                "discount": float(r["skidka"] or 0),
                "unit": r["ed_izmereniya"] or "",
                "quantity_in_stock": int(r["kolvo_na_sklade"] or 0),
                "image_path": r["photo"],
            })
        return result

    def get_suppliers(self) -> list[str]:
        """Возвращает список всех поставщиков из таблицы tovar."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT DISTINCT postavschik FROM tovar WHERE postavschik IS NOT NULL ORDER BY postavschik")
            return [r["postavschik"] for r in cur.fetchall()]

    def get_categories(self) -> list[str]:
        """Возвращает список всех категорий товаров."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT DISTINCT category_tovara FROM tovar WHERE category_tovara IS NOT NULL ORDER BY category_tovara")
            return [r["category_tovara"] for r in cur.fetchall()]

    def get_manufacturers(self) -> list[str]:
        """Возвращает список всех производителей."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT DISTINCT proizvoditel FROM tovar WHERE proizvoditel IS NOT NULL ORDER BY proizvoditel")
            return [r["proizvoditel"] for r in cur.fetchall()]

    def get_units(self) -> list[str]:
        """Возвращает список всех единиц измерения."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT DISTINCT ed_izmereniya FROM tovar WHERE ed_izmereniya IS NOT NULL ORDER BY ed_izmereniya")
            return [r["ed_izmereniya"] for r in cur.fetchall()]

    def save_product(
        self,
        *,
        product_id: str | None,
        article: str,
        name: str,
        category: str,
        description: str,
        manufacturer: str,
        supplier: str,
        price: float,
        discount: float,
        unit: str,
        quantity_in_stock: int,
        image_path: str | None,
    ) -> None:
        """Добавляет или обновляет товар в таблице tovar."""
        with self.connection.cursor() as cur:
            if product_id is None:
                cur.execute(
                    """INSERT INTO tovar (articul, name_tovara, category_tovara, description, proizvoditel, postavschik,
                       cost, skidka, ed_izmereniya, kolvo_na_sklade, photo)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (article, name, category, description, manufacturer, supplier, price, discount, unit, quantity_in_stock, image_path),
                )
            else:
                cur.execute(
                    """UPDATE tovar SET name_tovara=%s, category_tovara=%s, description=%s, proizvoditel=%s, postavschik=%s,
                       cost=%s, skidka=%s, ed_izmereniya=%s, kolvo_na_sklade=%s, photo=%s WHERE articul=%s""",
                    (name, category, description, manufacturer, supplier, price, discount, unit, quantity_in_stock, image_path, product_id),
                )
        self.connection.commit()

    def delete_product(self, product_id: str) -> bool:
        """Удаляет товар, если он не используется в заказах. Возвращает True/False."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM zakaz_import WHERE artikul_zakaza = %s", (product_id,))
            row = cur.fetchone()
            if row and row["cnt"] > 0:
                return False
            cur.execute("DELETE FROM tovar WHERE articul = %s", (product_id,))
        self.connection.commit()
        return True

    def get_orders(self) -> list[dict]:
        """Возвращает список всех заказов с адресом пункта выдачи."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT z.num_zakaza, z.artikul_zakaza, z.status_zakaza, z.data_zakaza, z.data_dostavki,
                          p.adress AS pickup_address
                   FROM zakaz_import z
                   LEFT JOIN LATERAL (
                       SELECT adress FROM (
                           SELECT adress, row_number() OVER () AS rn FROM punkty_vydachi_import
                       ) sub WHERE rn = z.adress_punkta_vydachi
                   ) p ON true
                   ORDER BY z.num_zakaza"""
            )
            rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r["num_zakaza"],
                "product_article": r["artikul_zakaza"],
                "status": r["status_zakaza"],
                "pickup_address": r["pickup_address"] or "",
                "order_date": r["data_zakaza"] or "",
                "delivery_date": r["data_dostavki"],
            })
        return result

    def get_order_statuses(self) -> list[str]:
        """Возвращает список всех статусов заказов."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT DISTINCT status_zakaza FROM zakaz_import WHERE status_zakaza IS NOT NULL ORDER BY status_zakaza")
            return [r["status_zakaza"] for r in cur.fetchall()]

    def get_pickup_addresses(self) -> list[str]:
        """Возвращает список адресов пунктов выдачи."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT adress FROM punkty_vydachi_import ORDER BY ctid")
            return [r["adress"] for r in cur.fetchall()]

    def get_product_articles(self) -> list[str]:
        """Возвращает список всех артикулов товаров."""
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT articul FROM tovar ORDER BY articul")
            return [r["articul"] for r in cur.fetchall()]

    def _address_to_index(self, address: str) -> int | None:
        """Преобразует текстовый адрес пункта выдачи в его порядковый номер."""
        addrs = self.get_pickup_addresses()
        for i, a in enumerate(addrs, 1):
            if a == address:
                return i
        return None

    def save_order(
        self,
        *,
        order_id: int | None,
        article: str,
        status: str,
        pickup_address: str,
        order_date: str,
        delivery_date: str | None,
    ) -> None:
        """Добавляет новый заказ или обновляет существующий в таблице zakaz_import."""
        idx = self._address_to_index(pickup_address)
        if idx is None:
            raise ValueError("Адрес пункта выдачи не найден в справочнике")
        with self.connection.cursor() as cur:
            if order_id is None:
                cur.execute(
                    """
                    INSERT INTO zakaz_import (
                        num_zakaza,
                        artikul_zakaza,
                        data_zakaza,
                        data_dostavki,
                        adress_punkta_vydachi,
                        status_zakaza
                    )
                    SELECT
                        COALESCE(MAX(num_zakaza), 0) + 1,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    FROM zakaz_import
                    """,
                    (article, order_date, delivery_date, idx, status),
                )
            else:
                cur.execute(
                    """UPDATE zakaz_import SET artikul_zakaza=%s, status_zakaza=%s, adress_punkta_vydachi=%s,
                       data_zakaza=%s, data_dostavki=%s WHERE num_zakaza=%s""",
                    (article, status, idx, order_date, delivery_date, order_id),
                )
        self.connection.commit()

    def delete_order(self, order_id: int | None) -> None:
        """Удаляет заказ по его номеру (учитывает возможные битые записи с NULL)."""
        try:
            with self.connection.cursor() as cur:
                # Особый случай для "битых" заказов, у которых num_zakaza = NULL
                if order_id is None or str(order_id) == "None":
                    cur.execute("DELETE FROM zakaz_import WHERE num_zakaza IS NULL")
                else:
                    cur.execute("DELETE FROM zakaz_import WHERE num_zakaza = %s", (int(order_id),))
            self.connection.commit()
        except psycopg2.Error:
            self.connection.rollback()
            raise

    def close(self) -> None:
        """Закрывает соединение с базой данных."""
        self.connection.close()


class Application(tk.Tk):
    def __init__(self, database: Database) -> None:
        """Главное окно приложения и переключатель между экранами."""
        super().__init__()
        self.title("Учебное приложение: Обувной магазин")
        self.configure(bg=BACKGROUND_MAIN)
        self.option_add("*Font", "Times 12")
        self.option_add("*Label.Font", "Times 12")
        self.option_add("*Button.Font", "Times 12 bold")
        self.geometry("1100x600")
        self.resizable(True, True)

        # Значок окна
        if ICON_ICO.exists():
            try:
                self.iconbitmap(default=str(ICON_ICO))
            except Exception:
                pass

        # Логотип (PNG) для использования в формах
        self.logo_image: tk.PhotoImage | None = None
        if ICON_PNG.exists():
            try:
                self.logo_image = tk.PhotoImage(file=str(ICON_PNG))
            except Exception:
                self.logo_image = None

        self.database = database
        self.current_user = None  # экземпляр User или None

        container = tk.Frame(self, bg=BACKGROUND_MAIN)
        container.pack(fill=tk.BOTH, expand=True)

        self.frames: dict[type[tk.Frame], tk.Frame] = {}
        for frame_class in (LoginFrame, ProductListFrame, OrderListFrame):
            frame = frame_class(parent=container, controller=self)
            self.frames[frame_class] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.show_frame(LoginFrame)

    def show_frame(self, frame_class: type[tk.Frame]) -> None:
        """Показывает нужный экран (фрейм) и обновляет его данные."""
        frame = self.frames[frame_class]
        if isinstance(frame, BaseFrame):
            frame.refresh()
        frame.tkraise()

    def login_as_guest(self) -> None:
        """Вход в систему в роли гостя."""
        self.current_user = User(id=-1, login="guest", full_name="Гость", role="Гость")
        self.show_frame(ProductListFrame)

    def login(self, login: str, password: str) -> None:
        """Попытка входа под учетной записью из базы данных."""
        user = self.database.get_user(login, password)
        if not user:
            messagebox.showerror("Ошибка входа", "Неверный логин или пароль.")
            return
        self.current_user = user
        self.show_frame(ProductListFrame)

    def logout(self) -> None:
        """Выход из учетной записи и возврат на экран авторизации."""
        self.current_user = None
        self.show_frame(LoginFrame)

    def open_orders(self) -> None:
        """Открывает экран заказов (доступно менеджеру и администратору)."""
        if not self.current_user or self.current_user.role not in {"Менеджер", "Администратор"}:
            messagebox.showinfo("Недостаточно прав", "Доступ к заказам есть только у менеджера и администратора.")
            return
        self.show_frame(OrderListFrame)


class BaseFrame(tk.Frame):
    def __init__(self, parent: tk.Widget, controller: Application) -> None:
        super().__init__(parent, bg=BACKGROUND_MAIN)
        self.controller = controller

    def refresh(self) -> None:
        """Вызывается при показе фрейма для обновления данных."""
        ...


class LoginFrame(BaseFrame):
    def __init__(self, parent: tk.Widget, controller: Application) -> None:
        """Экран авторизации пользователя (логин/пароль или вход как гость)."""
        super().__init__(parent, controller)
        if controller.logo_image is not None:
            logo_label = tk.Label(self, image=controller.logo_image, bg=BACKGROUND_MAIN)
            logo_label.image = controller.logo_image
            logo_label.pack(pady=(20, 5))
        title = tk.Label(self, text="Вход в систему", font=("Times New Roman", 18, "bold"), bg=BACKGROUND_MAIN)
        title.pack(pady=10)
        form_frame = tk.Frame(self, bg=BACKGROUND_SECONDARY)
        form_frame.pack(padx=40, pady=20)
        tk.Label(form_frame, text="Логин:", bg=BACKGROUND_SECONDARY).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        tk.Label(form_frame, text="Пароль:", bg=BACKGROUND_SECONDARY).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.login_entry = tk.Entry(form_frame)
        self.password_entry = tk.Entry(form_frame, show="*")
        self.login_entry.grid(row=0, column=1, padx=10, pady=10)
        self.password_entry.grid(row=1, column=1, padx=10, pady=10)
        buttons_frame = tk.Frame(self, bg=BACKGROUND_MAIN)
        buttons_frame.pack(pady=20)
        tk.Button(buttons_frame, text="Войти", bg=ACCENT_COLOR, command=self._on_login_clicked).grid(row=0, column=0, padx=10)
        tk.Button(buttons_frame, text="Войти как гость", command=self.controller.login_as_guest).grid(row=0, column=1, padx=10)

    def _on_login_clicked(self) -> None:
        """Обработчик нажатия кнопки 'Войти'."""
        login = self.login_entry.get().strip()
        password = self.password_entry.get().strip()
        if not login or not password:
            messagebox.showwarning("Некорректные данные", "Введите логин и пароль.")
            return
        self.controller.login(login, password)


class ProductListFrame(BaseFrame):
    def __init__(self, parent: tk.Widget, controller: Application) -> None:
        """Экран со списком товаров в виде карточек."""
        super().__init__(parent, controller)

        header = tk.Frame(self, bg=BACKGROUND_SECONDARY)
        header.pack(fill=tk.X)
        if controller.logo_image is not None:
            logo_small = tk.Label(header, image=controller.logo_image, bg=BACKGROUND_SECONDARY)
            logo_small.image = controller.logo_image
            logo_small.pack(side=tk.LEFT, padx=5, pady=5)
        tk.Label(header, text="Список товаров", font=("Times New Roman", 16, "bold"), bg=BACKGROUND_SECONDARY).pack(side=tk.LEFT, padx=10, pady=5)
        self.user_label = tk.Label(header, text="", bg=BACKGROUND_SECONDARY)
        self.user_label.pack(side=tk.RIGHT, padx=10)

        top_controls = tk.Frame(self, bg=BACKGROUND_MAIN)
        top_controls.pack(fill=tk.X, padx=10, pady=5)
        self.search_var = tk.StringVar()
        tk.Label(top_controls, text="Поиск:", bg=BACKGROUND_MAIN).pack(side=tk.LEFT)
        self.search_entry = tk.Entry(top_controls, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<KeyRelease>", lambda _: self._apply_filters())
        tk.Label(top_controls, text="Сортировка:", bg=BACKGROUND_MAIN).pack(side=tk.LEFT, padx=(20, 5))
        self.sort_var = tk.StringVar(value="Без сортировки")
        self.sort_combo = ttk.Combobox(top_controls, textvariable=self.sort_var, state="readonly", width=25,
            values=["Без сортировки", "Количество по возрастанию", "Количество по убыванию"])
        self.sort_combo.pack(side=tk.LEFT)
        self.sort_combo.bind("<<ComboboxSelected>>", lambda _: self._apply_filters())
        tk.Label(top_controls, text="Поставщик:", bg=BACKGROUND_MAIN).pack(side=tk.LEFT, padx=(20, 5))
        self.supplier_var = tk.StringVar(value="Все поставщики")
        self.supplier_combo = ttk.Combobox(top_controls, textvariable=self.supplier_var, state="readonly", width=30)
        self.supplier_combo.pack(side=tk.LEFT)
        self.supplier_combo.bind("<<ComboboxSelected>>", lambda _: self._apply_filters())

        buttons_frame = tk.Frame(self, bg=BACKGROUND_MAIN)
        buttons_frame.pack(fill=tk.X, padx=10, pady=5)
        self.add_button = tk.Button(buttons_frame, text="Добавить товар", bg=ACCENT_COLOR, command=self._add_product)
        self.add_button.pack(side=tk.LEFT, padx=5)
        self.edit_button = tk.Button(buttons_frame, text="Редактировать товар", command=self._edit_product)
        self.edit_button.pack(side=tk.LEFT, padx=5)
        self.delete_button = tk.Button(buttons_frame, text="Удалить товар", command=self._delete_product)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        tk.Button(buttons_frame, text="Заказы", command=self.controller.open_orders).pack(side=tk.RIGHT, padx=5)
        tk.Button(buttons_frame, text="Выйти", command=self.controller.logout).pack(side=tk.RIGHT, padx=5)

        # Область со списком товаров в виде карточек (как в макете)
        list_container = tk.Frame(self, bg=BACKGROUND_MAIN)
        list_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.cards_canvas = tk.Canvas(list_container, bg=BACKGROUND_MAIN, highlightthickness=0)
        self.cards_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(list_container, orient="vertical", command=self.cards_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.cards_canvas.configure(yscrollcommand=scrollbar.set)

        self.cards_frame = tk.Frame(self.cards_canvas, bg=BACKGROUND_MAIN)
        self.cards_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")

        def _on_frame_configure(_event: object) -> None:
            self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all"))

        self.cards_frame.bind("<Configure>", _on_frame_configure)

        self._all_products = []
        self._product_dialog = None
        self._selected_product_article = None
        self._selected_card = None

    def refresh(self) -> None:
        """Обновляет список товаров и состояние элементов в зависимости от роли."""
        user = self.controller.current_user
        self.user_label.config(text=f"{user.full_name} ({user.role})" if user else "")
        can_search = user and user.role in {"Менеджер", "Администратор"}
        for w in (self.search_entry, self.sort_combo, self.supplier_combo):
            w.configure(state="normal" if can_search else "disabled")
        is_admin = user and user.role == "Администратор"
        for b in (self.add_button, self.edit_button, self.delete_button):
            b.configure(state="normal" if is_admin else "disabled")
        suppliers = self.controller.database.get_suppliers()
        self.supplier_combo["values"] = ["Все поставщики", *suppliers]
        self.supplier_var.set("Все поставщики")
        self._all_products = self.controller.database.get_products()
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Применяет поиск, сортировку и фильтрацию по поставщику к списку товаров."""
        search_text = self.search_var.get().lower().strip()
        selected_supplier = self.supplier_var.get()
        sort_mode = self.sort_var.get()

        filtered = [
            p
            for p in self._all_products
            if (selected_supplier == "Все поставщики" or p["supplier"] == selected_supplier)
            and (
                not search_text
                or search_text
                in " ".join(
                    [
                        str(p.get("article", "")),
                        str(p.get("name", "")),
                        str(p.get("category", "")),
                        str(p.get("description", "") or ""),
                        str(p.get("manufacturer", "")),
                        str(p.get("supplier", "")),
                    ]
                ).lower()
            )
        ]

        reverse = sort_mode == "Количество по убыванию"

        if "Количество" in sort_mode:
            filtered.sort(key=lambda r: int(r.get("quantity_in_stock") or 0), reverse=reverse)
        else:
            filtered.sort(key=lambda r: str(r.get("article") or ""), reverse=False)

        # Перерисовываем карточки
        for child in self.cards_frame.winfo_children():
            child.destroy()
        self._selected_product_article = None
        self._selected_card = None

        for p in filtered:
            self._create_product_card(p)

    def _get_selected_product_id(self) -> str | None:
        """Возвращает артикул выбранного товара или None, если ничего не выбрано."""
        if not self._selected_product_article:
            messagebox.showinfo("Выбор товара", "Выберите товар в списке.")
            return None
        return self._selected_product_article   # артикул товара

    def _load_card_image(self, image_path):
        """Загружает изображение товара для карточки.

        В БД может быть только имя файла (например, 1.jpg), поэтому
        по умолчанию ищем картинку в папке assets/images.
        """
        # Определяем путь
        if image_path:
            p = Path(image_path)
            if not p.is_absolute():
                p = IMAGES_DIR / p.name
        else:
            p = PLACEHOLDER_IMAGE if PLACEHOLDER_IMAGE.exists() else None

        if p is None or not p.exists():
            # Если файла нет – рисуем пустой белый прямоугольник 300x200
            img = Image.new("RGB", (300, 200), "white")
            return ImageTk.PhotoImage(img)

        # Пытаемся открыть реальное изображение
        try:
            img = Image.open(p)
            img = img.convert("RGB")
            img = img.resize((300, 200))
        except Exception:
            img = Image.new("RGB", (300, 200), "white")

        return ImageTk.PhotoImage(img)

    def _create_product_card(self, product: dict) -> None:
        """Создаёт виджет-карточку товара по макету из задания."""
        article = product["article"]
        discount = float(product["discount"] or 0)
        qty = int(product["quantity_in_stock"] or 0)
        final_price = product["price"] * (1.0 - discount / 100.0)

        # Цвет фона по условиям задания
        bg = BACKGROUND_MAIN
        if qty == 0:
            bg = OUT_OF_STOCK_BACKGROUND
        elif discount > 15.0:
            bg = DISCOUNT_BACKGROUND

        card = tk.Frame(self.cards_frame, bg=bg, bd=1, relief="solid", padx=5, pady=5)
        card.pack(fill=tk.X, pady=3)

        # Левая часть: фото
        left = tk.Frame(card, bg=bg)
        left.pack(side=tk.LEFT, padx=5, pady=5)
        image = self._load_card_image(product.get("image_path"))
        img_label = tk.Label(left, image=image, bg=bg)
        img_label.image = image
        img_label.pack()

        # Центральная часть: текстовые данные
        center = tk.Frame(card, bg=bg)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        title = tk.Label(
            center,
            text=f"{product['category']} | {product['name']}",
            bg=bg,
            font=("Times New Roman", 12, "bold"),
            anchor="w",
        )
        title.pack(fill=tk.X)
        tk.Label(center, text=f"Описание товара: {product['description']}", bg=bg, anchor="w", justify="left").pack(
            fill=tk.X
        )
        tk.Label(center, text=f"Производитель: {product['manufacturer']}", bg=bg, anchor="w").pack(fill=tk.X)
        tk.Label(center, text=f"Поставщик: {product['supplier']}", bg=bg, anchor="w").pack(fill=tk.X)

        # Цена и скидка — старая цена перечеркнута, новая рядом
        price_frame = tk.Frame(center, bg=bg)
        price_frame.pack(fill=tk.X)
        if discount > 0:
            old_price_label = tk.Label(
                price_frame,
                text=f"Цена: {product['price']:.2f}",
                bg=bg,
                fg="red",
                font=("Times New Roman", 12, "overstrike"),
            )
            old_price_label.pack(side=tk.LEFT)
            new_price_label = tk.Label(
                price_frame,
                text=f"   Итоговая цена: {final_price:.2f}",
                bg=bg,
                fg="black",
            )
            new_price_label.pack(side=tk.LEFT)
        else:
            tk.Label(price_frame, text=f"Цена: {product['price']:.2f}", bg=bg, anchor="w").pack(side=tk.LEFT)

        tk.Label(center, text=f"Единица измерения: {product['unit']}", bg=bg, anchor="w").pack(fill=tk.X)
        tk.Label(center, text=f"Количество на складе: {qty}", bg=bg, anchor="w").pack(fill=tk.X)

        # Правая часть: действующая скидка
        right = tk.Frame(card, bg=bg)
        right.pack(side=tk.RIGHT, padx=10, pady=5)
        tk.Label(right, text="Действующая\nскидка", bg=bg, justify="center").pack()
        tk.Label(
            right,
            text=f"{discount:.0f}%",
            bg=bg,
            font=("Times New Roman", 14, "bold"),
            justify="center",
        ).pack()

        # Обработчики выбора и двойного клика
        def on_click(_event: object) -> None:
            self._select_card(article, card)

        def on_double_click(_event: object) -> None:
            self._select_card(article, card)
            self._edit_product()

        for widget in (card, left, center, right, img_label, title):
            widget.bind("<Button-1>", on_click)
            widget.bind("<Double-1>", on_double_click)

    def _select_card(self, article: str, card: tk.Widget) -> None:
        """Выделяет карточку товара и запоминает её артикул."""
        # сбрасываем предыдущий выбор
        if self._selected_card is not None:
            try:
                self._selected_card.configure(highlightthickness=0)
            except tk.TclError:
                pass
        self._selected_product_article = article
        self._selected_card = card
        try:
            card.configure(highlightthickness=2, highlightbackground="black")
        except tk.TclError:
            pass

    def _add_product(self) -> None:
        # Добавление товара доступно только администратору (кнопка уже отключается в refresh)
        self._open_product_dialog(product_id=None, readonly=False)

    def _edit_product(self) -> None:
        """Открывает карточку товара для редактирования (для админа) или просмотра (для остальных)."""
        pid = self._get_selected_product_id()
        if pid is None:
            return
        user = self.controller.current_user
        is_admin = bool(user and user.role == "Администратор")
        # Для не-админа открываем карточку товара только для просмотра (readonly)
        self._open_product_dialog(product_id=pid, readonly=not is_admin)

    def _open_product_dialog(self, product_id: str | None, readonly: bool = False) -> None:
        """Создаёт окно добавления/редактирования товара. Одновременно открыто только одно окно."""
        if self._product_dialog is not None and self._product_dialog.winfo_exists():
            messagebox.showinfo("Редактирование товара", "Сначала закройте открытое окно редактирования товара.")
            return
        dlg = ProductEditDialog(self, self.controller.database, product_id=product_id, readonly=readonly)
        self._product_dialog = dlg
        # Ждём закрытия окна модального диалога и только после этого обновляем список
        self.wait_window(dlg)
        self._product_dialog = None
        self._refresh_after_edit()

    def _delete_product(self) -> None:
        """Удаляет выбранный товар (если он не используется в заказах)."""
        pid = self._get_selected_product_id()
        if pid is None:
            return
        if not messagebox.askyesno("Удаление товара", "Вы действительно хотите удалить выбранный товар?"):
            return
        if not self.controller.database.delete_product(pid):
            messagebox.showwarning("Удаление запрещено", "Нельзя удалить товар, который уже присутствует в заказе.")
            return
        self._refresh_after_edit()

    def _refresh_after_edit(self) -> None:
        """Повторно загружает список товаров после изменения данных."""
        self._all_products = self.controller.database.get_products()
        self._apply_filters()


class OrderListFrame(BaseFrame):
    def __init__(self, parent: tk.Widget, controller: Application) -> None:
        """Экран со списком заказов (доступен менеджеру и администратору)."""
        super().__init__(parent, controller)
        header = tk.Frame(self, bg=BACKGROUND_SECONDARY)
        header.pack(fill=tk.X)
        tk.Label(header, text="Заказы", font=("Times New Roman", 16, "bold"), bg=BACKGROUND_SECONDARY).pack(side=tk.LEFT, padx=10, pady=5)
        self.user_label = tk.Label(header, text="", bg=BACKGROUND_SECONDARY)
        self.user_label.pack(side=tk.RIGHT, padx=10)
        buttons_frame = tk.Frame(self, bg=BACKGROUND_MAIN)
        buttons_frame.pack(fill=tk.X, padx=10, pady=5)
        self.add_button = tk.Button(buttons_frame, text="Добавить заказ", bg=ACCENT_COLOR, command=self._add_order)
        self.add_button.pack(side=tk.LEFT, padx=5)
        self.edit_button = tk.Button(buttons_frame, text="Редактировать заказ", command=self._edit_order)
        self.edit_button.pack(side=tk.LEFT, padx=5)
        self.delete_button = tk.Button(buttons_frame, text="Удалить заказ", command=self._delete_order)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        tk.Button(buttons_frame, text="Назад к товарам", command=lambda: self.controller.show_frame(ProductListFrame)).pack(side=tk.RIGHT, padx=5)
        columns = ("id", "article", "status", "pickup_address", "order_date", "delivery_date")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        for h, t in [
            ("id", "№ заказа"),
            ("article", "Артикул товара"),
            ("status", "Статус заказа"),
            ("pickup_address", "Адрес пункта выдачи"),
            ("order_date", "Дата заказа"),
            ("delivery_date", "Дата доставки")
        ]:
            self.tree.heading(h, text=t)
        for c in columns:
            self.tree.column(c, anchor="w", width=150)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.tree.bind("<Double-1>", lambda _: self._edit_order())
        self._orders: list[dict] = []
        self._order_dialog: "OrderEditDialog | None" = None

    def refresh(self) -> None:
        """Обновляет таблицу заказов и состояние кнопок в зависимости от роли."""
        user = self.controller.current_user
        self.user_label.config(text=f"{user.full_name} ({user.role})" if user else "")
        is_admin = user and user.role == "Администратор"
        for b in (self.add_button, self.edit_button, self.delete_button):
            b.configure(state="normal" if is_admin else "disabled")
        self._orders = self.controller.database.get_orders()
        for row_id in self.tree.get_children():
            self.tree.delete(row_id)
        for o in self._orders:
            self.tree.insert("", tk.END, values=(
                o["id"],  # добавляем ID в таблицу
                o["product_article"],
                o["status"],
                o["pickup_address"],
                o["order_date"],
                o["delivery_date"] or "",
            ))

    def _get_selected_order_id(self):
        """Возвращает номер выбранного заказа или None, если ничего не выбрано."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Выбор", "Выберите заказ")
            return None

        item = self.tree.item(sel[0])
        return item["values"][0]

    def _add_order(self) -> None:
        """Открывает окно добавления нового заказа (для администратора)."""
        self._open_order_dialog(order_id=None)

    def _edit_order(self) -> None:
        """Открывает окно редактирования выбранного заказа (для администратора)."""
        oid = self._get_selected_order_id()
        if oid is None:
            return
        self._open_order_dialog(order_id=oid)

    def _open_order_dialog(self, order_id: int | None) -> None:
        """Создаёт окно добавления/редактирования заказа. Одновременно открыто только одно окно."""
        if self._order_dialog is not None and self._order_dialog.winfo_exists():
            messagebox.showinfo("Редактирование заказа", "Сначала закройте открытое окно редактирования заказа.")
            return
        dlg = OrderEditDialog(self, self.controller.database, order_id=order_id)
        self._order_dialog = dlg
        # Ждём закрытия модального окна заказа
        self.wait_window(dlg)
        self._order_dialog = None
        self.refresh()

    def _delete_order(self) -> None:
        """Удаляет выбранный заказ после подтверждения."""
        oid = self._get_selected_order_id()
        if oid is None:
            return
        if not messagebox.askyesno("Удаление заказа", "Вы действительно хотите удалить выбранный заказ?"):
            return
        self.controller.database.delete_order(oid)
        self.refresh()


class ProductEditDialog(tk.Toplevel):
    def __init__(self, parent: ProductListFrame, database: Database, product_id: str | None, readonly: bool = False) -> None:
        """Окно добавления/редактирования товара."""
        super().__init__(parent)
        self.title("Товар")
        self.configure(bg=BACKGROUND_MAIN)
        self.transient(parent)
        self.grab_set()
        self.database = database
        self.product_id = product_id
        self.current_image_path: str | None = None
        self.readonly = readonly

        form = tk.Frame(self, bg=BACKGROUND_MAIN)
        form.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        row = 0
        tk.Label(form, text="Артикул:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.article_entry = tk.Entry(form)
        self.article_entry.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        if product_id:
            self.article_entry.config(state="readonly")
        row += 1
        tk.Label(form, text="Наименование:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.name_entry = tk.Entry(form)
        self.name_entry.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Категория:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(form, textvariable=self.category_var, state="readonly", values=database.get_categories())
        self.category_combo.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Описание:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="ne", padx=5, pady=5)
        self.description_text = tk.Text(form, height=4, width=40)
        self.description_text.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Производитель:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.manufacturer_var = tk.StringVar()
        self.manufacturer_combo = ttk.Combobox(form, textvariable=self.manufacturer_var, state="readonly", values=database.get_manufacturers())
        self.manufacturer_combo.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Поставщик:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.supplier_var = tk.StringVar()
        self.supplier_combo = ttk.Combobox(form, textvariable=self.supplier_var, state="readonly", values=database.get_suppliers())
        self.supplier_combo.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Цена:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.price_entry = tk.Entry(form)
        self.price_entry.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Скидка, %:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.discount_entry = tk.Entry(form)
        self.discount_entry.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Ед. измерения:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.unit_var = tk.StringVar()
        self.unit_combo = ttk.Combobox(form, textvariable=self.unit_var, state="readonly", values=database.get_units())
        self.unit_combo.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Количество на складе:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.quantity_entry = tk.Entry(form)
        self.quantity_entry.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Фото товара:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        image_frame = tk.Frame(form, bg=BACKGROUND_MAIN)
        image_frame.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        self.image_label = tk.Label(image_frame, text="Файл не выбран", bg=BACKGROUND_MAIN)
        self.image_label.pack(side=tk.LEFT, padx=5)
        self.choose_image_button = tk.Button(image_frame, text="Выбрать...", command=self._choose_image)
        self.choose_image_button.pack(side=tk.LEFT, padx=5)
        buttons = tk.Frame(self, bg=BACKGROUND_MAIN)
        buttons.pack(pady=10)
        self.save_button = tk.Button(buttons, text="Сохранить", bg=ACCENT_COLOR, command=self._save)
        self.save_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button = tk.Button(buttons, text="Отмена", command=self.destroy)
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        form.columnconfigure(1, weight=1)

        if self.product_id:
            self._load_product()

        if self.readonly:
            self._make_readonly()

    def _load_product(self) -> None:
        """Загружает данные выбранного товара из базы в поля формы."""
        products = [p for p in self.database.get_products() if p["article"] == self.product_id]
        if not products:
            messagebox.showerror("Ошибка", "Товар не найден.")
            self.destroy()
            return
        p = products[0]
        self.article_entry.insert(0, p["article"])
        self.name_entry.insert(0, p["name"])
        self.category_var.set(p["category"])
        self.description_text.insert("1.0", p["description"] or "")
        self.manufacturer_var.set(p["manufacturer"])
        self.supplier_var.set(p["supplier"])
        self.price_entry.insert(0, f"{p['price']:.2f}")
        self.discount_entry.insert(0, f"{p['discount']:.0f}")
        self.unit_var.set(p["unit"])
        self.quantity_entry.insert(0, str(p["quantity_in_stock"]))
        self.current_image_path = p.get("image_path")
        if self.current_image_path:
            self.image_label.config(text=self.current_image_path)

    def _choose_image(self) -> None:
        """Выбор файла изображения и сохранение его в папку assets/images с ресайзом до 300x200."""
        filename = filedialog.askopenfilename(title="Выбор изображения товара",
            filetypes=(("Изображения", "*.png;*.jpg;*.jpeg;*.gif"), ("Все файлы", "*.*")))
        if not filename:
            return
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        source = Path(filename)
        target = IMAGES_DIR / source.name
        if target.exists() and self.current_image_path != str(target):
            if not messagebox.askyesno("Файл существует", "Файл с таким именем уже существует. Перезаписать?"):
                return
        # Копируем файл
        target.write_bytes(source.read_bytes())
        # Пробуем привести изображение к размеру 300x200
        try:
            with Image.open(target) as img:
                img = img.convert("RGB")
                img = img.resize((300, 200))
                img.save(target)
        except Exception:
            # Если не удалось открыть / изменить как изображение – оставляем как есть
            pass
        if self.current_image_path:
            old = Path(self.current_image_path)
            if old.exists() and old != target:
                try:
                    old.unlink()
                except OSError:
                    pass
        self.current_image_path = str(target)
        self.image_label.config(text=self.current_image_path)

    def _make_readonly(self) -> None:
        # Блокируем изменение всех полей и кнопок, кроме "Отмена"
        for entry in (
            self.article_entry,
            self.name_entry,
            self.price_entry,
            self.discount_entry,
            self.quantity_entry,
        ):
            entry.config(state="readonly")
        for combo in (
            self.category_combo,
            self.manufacturer_combo,
            self.supplier_combo,
            self.unit_combo,
        ):
            combo.config(state="disabled")
        self.description_text.config(state="disabled")
        self.choose_image_button.config(state="disabled")
        self.save_button.config(state="disabled")

    def _save(self) -> None:
        """Проверяет введённые данные и сохраняет товар в базу."""
        try:
            price = float(self.price_entry.get().replace(",", "."))
            discount = float(self.discount_entry.get().replace(",", ".") or 0)
            quantity = int(self.quantity_entry.get())
        except ValueError:
            messagebox.showwarning("Некорректные данные", "Проверьте числовые поля: цена, скидка, количество.")
            return
        if price < 0 or discount < 0 or quantity < 0:
            messagebox.showwarning("Некорректные данные", "Цена, скидка и количество не могут быть отрицательными.")
            return
        article = self.product_id if self.product_id else self.article_entry.get().strip()

        name = self.name_entry.get().strip()
        category = self.category_var.get().strip()
        description = self.description_text.get("1.0", tk.END).strip()
        price = price
        discount = discount
        quantity = quantity
        manufacturer = self.manufacturer_var.get().strip()
        supplier = self.supplier_var.get().strip()
        unit = self.unit_var.get().strip()

        # проверяем артикул только при добавлении
        if not self.product_id and not article:
            messagebox.showerror("Ошибка", "Введите артикул")
            return

        if not all([name, category, manufacturer, supplier, unit]):
            messagebox.showerror(
                "Ошибка",
                "Заполните наименование, категорию, производителя, поставщика и единицу измерения"
            )
            return
        image_path = self.current_image_path or (str(PLACEHOLDER_IMAGE) if PLACEHOLDER_IMAGE.exists() else None)
        try:
            self.database.save_product(product_id=self.product_id, article=article, name=name, category=category,
                description=description, manufacturer=manufacturer, supplier=supplier, price=price, discount=discount,
                unit=unit, quantity_in_stock=quantity, image_path=image_path)
        except psycopg2.IntegrityError as e:
            self.database.connection.rollback()
            messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить товар: {e}")
            return
        self.destroy()


class OrderEditDialog(tk.Toplevel):
    def __init__(self, parent: OrderListFrame, database: Database, order_id: int | None) -> None:
        """Окно добавления/редактирования заказа."""
        super().__init__(parent)
        self.title("Заказ")
        self.configure(bg=BACKGROUND_MAIN)
        self.transient(parent)
        self.grab_set()
        self.database = database
        self.order_id = order_id

        form = tk.Frame(self, bg=BACKGROUND_MAIN)
        form.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        row = 0
        tk.Label(form, text="Артикул товара:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.article_var = tk.StringVar()
        self.article_combo = ttk.Combobox(form, textvariable=self.article_var, state="readonly", values=database.get_product_articles())
        self.article_combo.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Статус заказа:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.status_var = tk.StringVar()
        self.status_combo = ttk.Combobox(form, textvariable=self.status_var, state="readonly", values=database.get_order_statuses())
        self.status_combo.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Адрес пункта выдачи:", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.address_var = tk.StringVar()
        self.address_combo = ttk.Combobox(form, textvariable=self.address_var, state="readonly", values=database.get_pickup_addresses())
        self.address_combo.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Дата заказа (ГГГГ-ММ-ДД):", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.order_date_entry = tk.Entry(form)
        self.order_date_entry.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        row += 1
        tk.Label(form, text="Дата выдачи (ГГГГ-ММ-ДД):", bg=BACKGROUND_MAIN).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.delivery_date_entry = tk.Entry(form)
        self.delivery_date_entry.grid(row=row, column=1, sticky="we", padx=5, pady=5)
        buttons = tk.Frame(self, bg=BACKGROUND_MAIN)
        buttons.pack(pady=10)
        tk.Button(buttons, text="Сохранить", bg=ACCENT_COLOR, command=self._save).pack(side=tk.LEFT, padx=5)
        tk.Button(buttons, text="Отмена", command=self.destroy).pack(side=tk.LEFT, padx=5)
        form.columnconfigure(1, weight=1)

        if self.order_id:
            self._load_order()

    def _load_order(self) -> None:
        """Подгружает данные выбранного заказа в поля формы."""
        orders = [o for o in self.database.get_orders() if o["id"] == self.order_id]
        if not orders:
            messagebox.showerror("Ошибка", "Заказ не найден.")
            self.destroy()
            return
        o = orders[0]
        self.article_var.set(o["product_article"])
        self.status_var.set(o["status"])
        self.address_var.set(o["pickup_address"])
        self.order_date_entry.insert(0, o["order_date"])
        if o["delivery_date"]:
            self.delivery_date_entry.insert(0, o["delivery_date"])

    def _save(self) -> None:
        """Проверяет данные и сохраняет заказ в базу."""
        article = self.article_var.get().strip()
        status = self.status_var.get().strip()
        address = self.address_var.get().strip()
        order_date = self.order_date_entry.get().strip()
        delivery_date = self.delivery_date_entry.get().strip() or None
        if not article or not status or not address or not order_date:
            messagebox.showwarning("Обязательные поля", "Заполните артикул, статус, адрес и дату заказа.")
            return
        try:
            self.database.save_order(order_id=self.order_id, article=article, status=status, pickup_address=address,
                order_date=order_date, delivery_date=delivery_date)
        except (psycopg2.IntegrityError, ValueError) as e:
            self.database.connection.rollback()
            messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить заказ: {e}")
            return
        self.destroy()


def main() -> None:
    try:
        database = Database()
    except psycopg2.OperationalError as e:
        messagebox.showerror(
            "Ошибка подключения",
            f"Не удалось подключиться к PostgreSQL (БД demoex).\n\n"
            f"Проверь:\n"
            f"1. PostgreSQL запущен\n"
            f"2. БД demoex создана и загружена из demoexam_db.sql\n"
            f"3. Параметры в db_config.py (host, user, password)\n\n"
            f"Ошибка: {e}",
        )
        return

    app = Application(database)

    def on_close() -> None:
        database.close()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
