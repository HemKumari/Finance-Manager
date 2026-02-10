# FinTrack Pro – CLI Finance Manager (Updated Version)
# Python + SQLite + SQLAlchemy

import sys
import os
from datetime import datetime, date, timedelta
from typing import Optional
import sqlalchemy as sa
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey1
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.exc import SQLAlchemyError

# ────────────────────────────────────────────────
#                     DATABASE SETUP
# ────────────────────────────────────────────────

Base = declarative_base()
engine = create_engine("sqlite:///fintrack.db", echo=False)
Session = sessionmaker(bind=engine)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    expenses = relationship("Expense", back_populates="category")

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False, default=date.today)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    category = relationship("Category", back_populates="expenses")

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True)
    month = Column(String(7), nullable=False, unique=True)  # YYYY-MM
    limit = Column(Float, nullable=False)

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    next_date = Column(Date, nullable=False)

# Create tables
Base.metadata.create_all(engine)

# ────────────────────────────────────────────────
#                     HELPER FUNCTIONS
# ────────────────────────────────────────────────

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_or_create_category(session, name: str) -> Category:
    name = name.strip().lower()
    cat = session.query(Category).filter_by(name=name).first()
    if not cat:
        cat = Category(name=name)
        session.add(cat)
        session.commit()
    return cat

def get_current_month() -> str:
    return datetime.now().strftime("%Y-%m")

def parse_date(date_str: str) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

def color(text: str, code: str) -> str:
    colors = {
        "red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
        "cyan": "\033[96m", "reset": "\033[0m"
    }
    return f"{colors.get(code, '')}{text}{colors['reset']}"

# ────────────────────────────────────────────────
#                     CORE FUNCTIONS
# ────────────────────────────────────────────────

def add_expense(title: str, amount: float, category_name: str, exp_date: str = ""):
    session = Session()
    try:
        cat = get_or_create_category(session, category_name)
        d = parse_date(exp_date) or date.today()
        
        expense = Expense(title=title.strip(), amount=amount, date=d, category=cat)
        session.add(expense)
        session.commit()
        print(color(f"✓ Added: {title} ₹{amount:.2f} ({cat.name}) on {d}", "green"))
    except SQLAlchemyError as e:
        session.rollback()
        print(color(f"Error: {e}", "red"))
    finally:
        session.close()

def delete_expense(expense_id: int):
    session = Session()
    try:
        exp = session.query(Expense).get(expense_id)
        if not exp:
            print(color(f"Expense #{expense_id} not found.", "red"))
            return
        title, amount, cat = exp.title, exp.amount, exp.category.name
        session.delete(exp)
        session.commit()
        print(color(f"Deleted: {title} ₹{amount:.2f} ({cat})", "yellow"))
    except SQLAlchemyError as e:
        session.rollback()
        print(color(f"Error: {e}", "red"))
    finally:
        session.close()

def list_expenses(limit: int = 15):
    session = Session()
    try:
        exps = (session.query(Expense)
                .order_by(Expense.date.desc(), Expense.id.desc())
                .limit(limit).all())
        
        if not exps:
            print("No expenses yet.")
            return
        
        print("\nRecent Expenses:")
        print("-"*70)
        for e in exps:
            print(f"#{e.id:4} | {e.date} | {e.title:<25} | ₹{e.amount:>8.2f} | {e.category.name}")
        print("-"*70)
    finally:
        session.close()

def search_expenses(start_date: str = "", end_date: str = ""):
    session = Session()
    try:
        query = session.query(Expense).order_by(Expense.date.desc())
        
        if start_date:
            sd = parse_date(start_date)
            if sd:
                query = query.filter(Expense.date >= sd)
            else:
                print(color("Invalid start date format (use YYYY-MM-DD)", "red"))
        
        if end_date:
            ed = parse_date(end_date)
            if ed:
                query = query.filter(Expense.date <= ed)
            else:
                print(color("Invalid end date format (use YYYY-MM-DD)", "red"))
        
        results = query.all()
        
        if not results:
            print("No expenses found in this date range.")
            return
        
        print(f"\nExpenses found: {len(results)}")
        print("-"*70)
        for e in results:
            print(f"#{e.id:4} | {e.date} | {e.title:<25} | ₹{e.amount:>8.2f} | {e.category.name}")
        print("-"*70)
    finally:
        session.close()

def category_report(month: str = ""):
    if not month:
        month = get_current_month()
    
    session = Session()
    try:
        sql = """
        SELECT c.name, COALESCE(SUM(e.amount), 0) as total
        FROM categories c
        LEFT JOIN expenses e ON c.id = e.category_id
            AND strftime('%Y-%m', e.date) = :month
        GROUP BY c.name
        ORDER BY total DESC
        """
        result = session.execute(sa.text(sql), {"month": month}).fetchall()
        
        if not result or all(r[1] == 0 for r in result):
            print(f"No spending in {month}")
            return
        
        print(f"\nCategory Report – {month}")
        print("-"*50)
        total = 0
        for cat, amt in result:
            if amt > 0:
                print(f"{cat:18} ₹{amt:>10.2f}")
                total += amt
        print("-"*50)
        print(f"Total: ₹{total:>10.2f}")
    finally:
        session.close()

def budget_status():
    month = get_current_month()
    session = Session()
    try:
        budget = session.query(Budget).filter_by(month=month).first()
        if not budget:
            print(f"No budget set for {month}. Use option 7 to set.")
            return
        
        sql = """
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE strftime('%Y-%m', date) = :month
        """
        spent = session.execute(sa.text(sql), {"month": month}).scalar() or 0.0
        
        percent = (spent / budget.limit * 100) if budget.limit > 0 else 0
        status_color = "green" if percent < 80 else "yellow" if percent < 100 else "red"
        status_text = "GOOD" if percent < 80 else "CAUTION" if percent < 100 else "OVER BUDGET!"
        
        print(f"\nBudget {month}: ₹{budget.limit:,.2f}")
        print(f"Spent:        ₹{spent:,.2f} ({percent:.1f}%)")
        print(color(f"Status: {status_text}", status_color))
    finally:
        session.close()

def set_budget(limit: float, month: str = ""):
    if not month:
        month = get_current_month()
    session = Session()
    try:
        b = session.query(Budget).filter_by(month=month).first()
        if b:
            b.limit = limit
        else:
            b = Budget(month=month, limit=limit)
            session.add(b)
        session.commit()
        print(color(f"Budget set for {month}: ₹{limit:,.2f}", "green"))
    except SQLAlchemyError as e:
        session.rollback()
        print(color(f"Error: {e}", "red"))
    finally:
        session.close()

def add_subscription(name: str, amount: float, next_date_str: str):
    d = parse_date(next_date_str)
    if not d:
        print(color("Invalid date. Use YYYY-MM-DD", "red"))
        return
    
    session = Session()
    try:
        sub = Subscription(name=name.strip(), amount=amount, next_date=d)
        session.add(sub)
        session.commit()
        print(color(f"Subscription added: {name} ₹{amount:.2f} due on {d}", "green"))
    except SQLAlchemyError as e:
        session.rollback()
        print(color(f"Error: {e}", "red"))
    finally:
        session.close()

def list_upcoming_subscriptions(days: int = 30):
    session = Session()
    try:
        today = date.today()
        soon = today + timedelta(days=days)
        
        subs = (session.query(Subscription)
                .filter(Subscription.next_date <= soon)
                .order_by(Subscription.next_date)
                .all())
        
        if not subs:
            print(f"No subscriptions due in next {days} days.")
            return
        
        print(f"\nUpcoming Subscriptions (next {days} days):")
        print("-"*60)
        for s in subs:
            days_left = (s.next_date - today).days
            days_text = f"in {days_left} days" if days_left > 0 else "TODAY!" if days_left == 0 else f"{-days_left} days overdue"
            color_code = "red" if days_left <= 0 else "yellow" if days_left <= 7 else "green"
            print(color(f"{s.name:20} ₹{s.amount:>8.2f}  {s.next_date} ({days_text})", color_code))
        print("-"*60)
    finally:
        session.close()

# ────────────────────────────────────────────────
#                     MENU & MAIN LOOP
# ────────────────────────────────────────────────

def show_menu():
    clear_screen()
    print("\n" + "="*55)
    print("          FinTrack Pro - Personal Finance Manager")
    print("="*55)
    print(" 1. Add Expense")
    print(" 2. Delete Expense")
    print(" 3. List Recent Expenses")
    print(" 4. Search Expenses by Date Range")
    print(" 5. Category Report (current month)")
    print(" 6. Budget Status")
    print(" 7. Set Monthly Budget")
    print(" 8. Add Subscription")
    print(" 9. Show Upcoming Subscriptions")
    print("10. Clear Screen")
    print(" 0. Exit")
    print("="*55)

def main():
    print("FinTrack Pro starting... (SQLite database: fintrack.db)")
    
    while True:
        show_menu()
        choice = input("\nEnter your choice (0-10): ").strip()

        if choice == "0":
            print("\nThank you for using FinTrack Pro. Goodbye!")
            sys.exit(0)

        elif choice == "1":
            title = input("Title: ").strip()
            if not title:
                print(color("Title is required.", "red"))
                continue
            try:
                amount = float(input("Amount (₹): "))
                if amount <= 0:
                    raise ValueError
            except ValueError:
                print(color("Enter a valid positive amount.", "red"))
                continue
            category = input("Category: ").strip()
            if not category:
                print(color("Category is required.", "red"))
                continue
            date_str = input("Date (YYYY-MM-DD) [today]: ").strip()
            add_expense(title, amount, category, date_str)

        elif choice == "2":
            try:
                eid = int(input("Expense ID to delete: "))
                delete_expense(eid)
            except ValueError:
                print(color("Please enter a valid number.", "red"))

        elif choice == "3":
            list_expenses()

        elif choice == "4":
            print("\nEnter date range (leave empty to skip)")
            start = input("From (YYYY-MM-DD): ").strip()
            end = input("To (YYYY-MM-DD): ").strip()
            search_expenses(start, end)

        elif choice == "5":
            category_report()

        elif choice == "6":
            budget_status()

        elif choice == "7":
            try:
                limit = float(input("Monthly budget limit (₹): "))
                if limit <= 0:
                    raise ValueError
                set_budget(limit)
            except ValueError:
                print(color("Enter a valid positive number.", "red"))

        elif choice == "8":
            name = input("Subscription name: ").strip()
            if not name:
                print(color("Name required.", "red"))
                continue
            try:
                amount = float(input("Amount (₹): "))
                if amount <= 0:
                    raise ValueError
            except ValueError:
                print(color("Invalid amount.", "red"))
                continue
            next_date = input("Next due date (YYYY-MM-DD): ").strip()
            add_subscription(name, amount, next_date)

        elif choice == "9":
            list_upcoming_subscriptions()

        elif choice == "10":
            clear_screen()
            print(color("Screen cleared.", "cyan"))

        else:
            print(color("Invalid choice. Please try again.", "red"))

        input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExited by user.")
    except Exception as e:
        print(color(f"Unexpected error: {e}", "red"))
