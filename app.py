import os
from datetime import datetime
from shiny import App, render, ui, reactive
import pandas as pd
import mysql.connector
from mysql.connector import Error
import logging

# MySQL database configuration - all from environment variables
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'autocommit': True,
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

# Default categories (will be loaded from database)
DEFAULT_CATEGORIES = [
    "Relationship with God",
    "Spouse", 
    "Family",
    "Church",
    "Work-Education",
    "Community-Friends",
    "Hobbies-Interest"
]

STATUSES = ["Idea", "Open", "Closed"]

class DatabaseManager:
    def __init__(self):
        self.config = DATABASE_CONFIG
        self.init_database()
    
    def get_connection(self):
        try:
            conn = mysql.connector.connect(**self.config)
            return conn
        except Error as e:
            logging.error(f"Database connection error: {e}")
            return None
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            # Create categories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Create tasks table (updated to reference categories table)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    subject VARCHAR(255) NOT NULL,
                    category INT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'Idea',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (category) REFERENCES categories(id) ON DELETE RESTRICT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Create notes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_notes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    task_id INT,
                    note TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Insert default categories if categories table is empty
            cursor.execute("SELECT COUNT(*) FROM categories")
            count = cursor.fetchone()[0]
            
            if count == 0:
                for category in DEFAULT_CATEGORIES:
                    cursor.execute("INSERT INTO categories (name) VALUES (%s)", (category,))
            
            conn.commit()
        except Error as e:
            logging.error(f"Database initialization error: {e}")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    # Category CRUD operations
    def create_category(self, name):
        """Create a new category"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (name) VALUES (%s)", (name,))
            conn.commit()
            return True
        except Error as e:
            logging.error(f"Create category error: {e}")
            return False
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    def get_all_categories(self):
        """Get all categories"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM categories ORDER BY name")
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Get categories error: {e}")
            return []
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    def get_category_by_id(self, category):
        """Get a specific category by ID"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM categories WHERE id = %s", (category,))
            return cursor.fetchone()
        except Error as e:
            logging.error(f"Get category error: {e}")
            return None
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    def update_category(self, category, name):
        """Update a category"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE categories SET name = %s WHERE id = %s", (name, category))
            conn.commit()
            return True
        except Error as e:
            logging.error(f"Update category error: {e}")
            return False
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    def delete_category(self, category):
        """Delete a category (only if no tasks are using it)"""
        conn = self.get_connection()
        if not conn:
            return False, "Database connection error"
        
        try:
            cursor = conn.cursor()
            
            # Check if any tasks are using this category
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE category = %s", (category,))
            task_count = cursor.fetchone()[0]
            
            if task_count > 0:
                return False, f"Cannot delete category. {task_count} task(s) are using this category."
            
            cursor.execute("DELETE FROM categories WHERE id = %s", (category,))
            conn.commit()
            return True, "Category deleted successfully"
        except Error as e:
            logging.error(f"Delete category error: {e}")
            return False, f"Error deleting category: {e}"
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    def get_categories_dict(self):
        """Get categories as a dictionary for dropdown choices"""
        categories = self.get_all_categories()
        return {str(cat['id']): cat['name'] for cat in categories}
    
    # Task CRUD operations (updated to work with categories table)
    def create_task(self, subject, category, status, note=None):
        """Create a new task with optional initial note"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            # Insert task
            cursor.execute("""
                INSERT INTO tasks (subject, category, status) 
                VALUES (%s, %s, %s)
            """, (subject, category, status))
            
            task_id = cursor.lastrowid
            
            # Add initial note if provided
            if note and note.strip():
                cursor.execute("""
                    INSERT INTO task_notes (task_id, note) 
                    VALUES (%s, %s)
                """, (task_id, note.strip()))
            
            conn.commit()
            return True
        except Error as e:
            logging.error(f"Create task error: {e}")
            return False
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    def get_all_tasks(self):
        """Get all tasks with their notes and category names"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT t.*, c.name as category_name,
                       GROUP_CONCAT(tn.note ORDER BY tn.created_at SEPARATOR ' | ') as notes
                FROM tasks t
                JOIN categories c ON t.category = c.id
                LEFT JOIN task_notes tn ON t.id = tn.task_id
                GROUP BY t.id, t.subject, t.category, t.status, t.created_at, t.updated_at, c.name
                ORDER BY t.created_at DESC
            """)
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Get tasks error: {e}")
            return []
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    def search_tasks(self, search_term):
        """Search tasks by subject or category name"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT t.*, c.name as category_name,
                       GROUP_CONCAT(tn.note ORDER BY tn.created_at SEPARATOR ' | ') as notes
                FROM tasks t
                JOIN categories c ON t.category = c.id
                LEFT JOIN task_notes tn ON t.id = tn.task_id
                WHERE t.subject LIKE %s OR c.name LIKE %s
                GROUP BY t.id, t.subject, t.category, t.status, t.created_at, t.updated_at, c.name
                ORDER BY t.created_at DESC
            """, (f"'%{search_term}%'", f"'%{search_term}%'"))
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Search tasks error: {e}")
            return []
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    def get_task_by_id(self, task_id):
        """Get a specific task by ID"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            return cursor.fetchone()
        except Error as e:
            logging.error(f"Get task error: {e}")
            return None
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    def get_task_notes(self, task_id):
        """Get all notes for a specific task"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM task_notes 
                WHERE task_id = %s 
                ORDER BY created_at DESC
            """, (task_id,))
            return cursor.fetchall()
        except Error as e:
            logging.error(f"Get task notes error: {e}")
            return []
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    def update_task(self, task_id, subject, category, status):
        """Update a task"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tasks 
                SET subject = %s, category = %s, status = %s
                WHERE id = %s
            """, (subject, category, status, task_id))
            conn.commit()
            return True
        except Error as e:
            logging.error(f"Update task error: {e}")
            return False
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    def add_note_to_task(self, task_id, note):
        """Add a note to an existing task"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO task_notes (task_id, note) 
                VALUES (%s, %s)
            """, (task_id, note))
            conn.commit()
            return True
        except Error as e:
            logging.error(f"Add note error: {e}")
            return False
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    
    def delete_task(self, task_id):
        """Delete a task and all its notes"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            # MySQL with foreign keys will automatically delete related notes
            # But let's be explicit
            cursor.execute("DELETE FROM task_notes WHERE task_id = %s", (task_id,))
            cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            
            conn.commit()
            return True
        except Error as e:
            logging.error(f"Delete task error: {e}")
            return False
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

# Initialize database manager
db = DatabaseManager()

# Define UI
app_ui = ui.page_fluid(
    ui.h1("Task Manager with Category Management"),
    
    # Navigation tabs
    ui.navset_tab(
        ui.nav_panel("Tasks",
            ui.row(
                ui.column(6,
                    ui.card(
                        ui.card_header("Add New Task"),
                        ui.input_text("task_subject", "Task Subject:", placeholder="Enter task subject"),
                        ui.output_ui("task_category_select"),
                        ui.input_select("task_status", "Status:", choices=STATUSES, selected="Idea"),
                        ui.input_text_area("task_note", "Initial Note (Optional):", rows=3),
                        ui.input_action_button("add_task", "Add Task", class_="btn-primary")
                    )
                ),
                
                ui.column(6,
                    ui.card(
                        ui.card_header("Edit Task"),
                        ui.output_ui("edit_task_select"),
                        ui.input_text("edit_subject", "Subject:"),
                        ui.output_ui("edit_category_select"),
                        ui.input_select("edit_status", "Status:", choices=STATUSES),
                        ui.input_text_area("new_note", "Add Note:", rows=2),
                        ui.div(
                            ui.input_action_button("update_task", "Update Task", class_="btn-warning"),
                            ui.input_action_button("add_note", "Add Note", class_="btn-info"),
                            ui.input_action_button("delete_task", "Delete Task", class_="btn-danger"),
                            style="margin-top: 10px;"
                        )
                    )
                )
            ),
            
            ui.hr(),
            
            # Search Section
            ui.card(
                ui.card_header("Search Tasks"),
                ui.row(
                    ui.column(8,
                        ui.input_text("search_term", "Search by Subject or Category:", 
                                    placeholder="Enter search term...")
                    ),
                    ui.column(4,
                        ui.input_action_button("search_tasks", "Search", class_="btn-secondary"),
                        ui.input_action_button("clear_search", "Clear", class_="btn-outline-secondary", 
                                             style="margin-left: 10px;")
                    )
                )
            ),
            
            ui.hr(),
            
            # Search Results Section
            ui.output_ui("search_results_section"),
            
            ui.hr(),
            
            ui.card(
                ui.card_header("All Tasks"),
                ui.output_data_frame("tasks_table")
            ),
            
            ui.div(id="selected_task_notes", style="margin-top: 20px;"),
            ui.output_ui("task_notes_display")
        ),
        
        ui.nav_panel("Categories",
            ui.row(
                ui.column(6,
                    ui.card(
                        ui.card_header("Add New Category"),
                        ui.input_text("new_category_name", "Category Name:", placeholder="Enter category name"),
                        ui.input_action_button("add_category", "Add Category", class_="btn-primary"),
                        ui.div(id="add_category_message", style="margin-top: 10px;")
                    )
                ),
                
                ui.column(6,
                    ui.card(
                        ui.card_header("Edit Category"),
                        ui.output_ui("edit_category_dropdown"),
                        ui.input_text("edit_category_name", "Category Name:"),
                        ui.div(
                            ui.input_action_button("update_category", "Update Category", class_="btn-warning"),
                            ui.input_action_button("delete_category", "Delete Category", class_="btn-danger"),
                            style="margin-top: 10px;"
                        ),
                        ui.div(id="edit_category_message", style="margin-top: 10px;")
                    )
                )
            ),
            
            ui.hr(),
            
            ui.card(
                ui.card_header("All Categories"),
                ui.output_data_frame("categories_table")
            )
        )
    )
)

def server(input, output, session):
    # Reactive values to trigger refreshes
    refresh_tasks = reactive.Value(0)
    refresh_categories = reactive.Value(0)
    category_message = reactive.Value("")
    edit_category_message = reactive.Value("")
    search_results = reactive.Value([])
    show_search_results = reactive.Value(False)
    
    # Dynamic UI for category selects
    @output
    @render.ui
    def task_category_select():
        refresh_categories.get()  # Depend on category changes
        categories = db.get_categories_dict()
        return ui.input_select("task_category", "Category:", choices=categories)
    
    @output
    @render.ui
    def edit_category_select():
        refresh_categories.get()  # Depend on category changes
        categories = db.get_categories_dict()
        return ui.input_select("edit_category", "Category:", choices=categories)
    
    @output
    @render.ui
    def edit_task_select():
        refresh_tasks.get()  # Depend on task changes
        tasks = db.get_all_tasks()
        choices = {str(task['id']): f"{task['subject']} ({task['category_name']})" 
                  for task in tasks}
        return ui.input_select("edit_task_id", "Select Task to Edit:", choices=choices)
    
    @output
    @render.ui
    def edit_category_dropdown():
        refresh_categories.get()  # Depend on category changes
        categories = db.get_categories_dict()
        return ui.input_select("selected_category", "Select Category to Edit:", choices=categories)
    
    # Search functionality
    @reactive.Effect
    @reactive.event(input.search_tasks)
    def perform_search():
        if not input.search_term() or not input.search_term().strip():
            show_search_results.set(False)
            return
        
        results = db.search_tasks(input.search_term().strip())
        search_results.set(results)
        show_search_results.set(True)
    
    @reactive.Effect
    @reactive.event(input.clear_search)
    def clear_search():
        ui.update_text("search_term", value="")
        search_results.set([])
        show_search_results.set(False)
    
    @output
    @render.ui
    def search_results_section():
        if not show_search_results.get():
            return ui.div()
        
        results = search_results.get()
        
        if not results:
            return ui.card(
                ui.card_header("Search Results"),
                ui.p("No tasks found matching your search criteria.")
            )
        
        # Create clickable task items
        task_items = []
        for task in results:
            # Truncate notes for display
            notes_preview = task['notes'][:50] + '...' if task['notes'] and len(task['notes']) > 50 else task['notes'] or 'No notes'
            
            task_items.append(
                ui.div(
                    ui.input_action_button(
                        f"select_task_{task['id']}", 
                        f"{task['subject']} | {task['category_name']} | {task['status']}",
                        class_="btn-outline-primary btn-block",
                        style="text-align: left; margin-bottom: 5px; width: 100%;"
                    ),
                    ui.small(f"Notes: {notes_preview}", style="color: #666; display: block; margin-left: 10px;"),
                    style="margin-bottom: 10px;"
                )
            )
        
        return ui.card(
            ui.card_header(f"Search Results ({len(results)} task{'s' if len(results) != 1 else ''} found)"),
            ui.div(*task_items)
        )
    
    # Handle task selection from search results
    @reactive.Effect
    def handle_task_selection():
        # This will handle clicks on any search result task button
        for task in search_results.get():
            button_id = f"select_task_{task['id']}"
            
            # Create a closure to capture the task_id
            def make_handler(task_id):
                @reactive.Effect
                @reactive.event(getattr(input, button_id, lambda: 0))
                def select_task():
                    # Update the edit form with the selected task
                    ui.update_select("edit_task_id", selected=str(task_id))
                    
                    # Load the task data into the edit form
                    task_data = db.get_task_by_id(task_id)
                    if task_data:
                        ui.update_text("edit_subject", value=task_data['subject'])
                        ui.update_select("edit_category", selected=str(task_data['category']))
                        ui.update_select("edit_status", selected=task_data['status'])
                    
                    # Clear search results
                    show_search_results.set(False)
                    ui.update_text("search_term", value="")
                
                return select_task
            
            # Only create handler if the button input exists
            if hasattr(input, button_id):
                make_handler(task['id'])()
    
    # Category management
    @reactive.Effect
    @reactive.event(input.add_category)
    def add_new_category():
        if not input.new_category_name() or not input.new_category_name().strip():
            return
        
        success = db.create_category(input.new_category_name().strip())
        
        if success:
            ui.update_text("new_category_name", value="")
            category_message.set("Category added successfully!")
            refresh_categories.set(refresh_categories.get() + 1)
        else:
            category_message.set("Error adding category. It may already exist.")
    
    @reactive.Effect
    @reactive.event(input.selected_category)
    def update_category_form():
        if not input.selected_category():
            return
        
        category = db.get_category_by_id(int(input.selected_category()))
        if category:
            ui.update_text("edit_category_name", value=category['name'])
    
    @reactive.Effect
    @reactive.event(input.update_category)
    def update_existing_category():
        if not input.selected_category() or not input.edit_category_name():
            return
        
        success = db.update_category(int(input.selected_category()), input.edit_category_name())
        
        if success:
            edit_category_message.set("Category updated successfully!")
            refresh_categories.set(refresh_categories.get() + 1)
            refresh_tasks.set(refresh_tasks.get() + 1)  # Refresh tasks to show new category names
        else:
            edit_category_message.set("Error updating category.")
    
    @reactive.Effect
    @reactive.event(input.delete_category)
    def delete_existing_category():
        if not input.selected_category():
            return
        
        success, message = db.delete_category(int(input.selected_category()))
        edit_category_message.set(message)
        
        if success:
            ui.update_select("selected_category", selected="")
            ui.update_text("edit_category_name", value="")
            refresh_categories.set(refresh_categories.get() + 1)
    
    # Task management (updated for new category system)
    @reactive.Effect
    @reactive.event(input.add_task)
    def add_new_task():
        if not input.task_subject():
            return
        
        success = db.create_task(
            input.task_subject(),
            int(input.task_category()),
            input.task_status(),
            input.task_note()
        )
        
        if success:
            ui.update_text("task_subject", value="")
            ui.update_text_area("task_note", value="")
            refresh_tasks.set(refresh_tasks.get() + 1)
    
    @reactive.Effect
    @reactive.event(input.edit_task_id)
    def update_edit_form():
        if not input.edit_task_id():
            return
        
        task = db.get_task_by_id(int(input.edit_task_id()))
        if task:
            ui.update_text("edit_subject", value=task['subject'])
            ui.update_select("edit_category", selected=str(task['category']))
            ui.update_select("edit_status", selected=task['status'])
    
    @reactive.Effect
    @reactive.event(input.update_task)
    def update_existing_task():
        if not input.edit_task_id():
            return
        
        success = db.update_task(
            int(input.edit_task_id()),
            input.edit_subject(),
            int(input.edit_category()),
            input.edit_status()
        )
        
        if success:
            refresh_tasks.set(refresh_tasks.get() + 1)
    
    @reactive.Effect
    @reactive.event(input.add_note)
    def add_task_note():
        if not input.edit_task_id() or not input.new_note():
            return
        
        success = db.add_note_to_task(int(input.edit_task_id()), input.new_note())
        
        if success:
            ui.update_text_area("new_note", value="")
            refresh_tasks.set(refresh_tasks.get() + 1)
    
    @reactive.Effect
    @reactive.event(input.delete_task)
    def delete_existing_task():
        if not input.edit_task_id():
            return
        
        success = db.delete_task(int(input.edit_task_id()))
        
        if success:
            ui.update_select("edit_task_id", selected="")
            ui.update_text("edit_subject", value="")
            ui.update_text_area("new_note", value="")
            refresh_tasks.set(refresh_tasks.get() + 1)
    
    # Render tables
    @output
    @render.data_frame
    def tasks_table():
        refresh_tasks.get()
        tasks = db.get_all_tasks()
        
        if not tasks:
            return pd.DataFrame(columns=['ID', 'Subject', 'Category', 'Status', 'Created', 'Notes'])
        
        df_data = []
        for task in tasks:
            df_data.append({
                'ID': task['id'],
                'Subject': task['subject'],
                'Category': task['category_name'],
                'Status': task['status'],
                'Created': task['created_at'].strftime('%Y-%m-%d %H:%M') if task['created_at'] else '',
                'Notes': task['notes'][:100] + '...' if task['notes'] and len(task['notes']) > 100 else task['notes'] or ''
            })
        
        return pd.DataFrame(df_data)
    
    @output
    @render.data_frame
    def categories_table():
        refresh_categories.get()
        categories = db.get_all_categories()
        
        if not categories:
            return pd.DataFrame(columns=['ID', 'Name', 'Created'])
        
        df_data = []
        for category in categories:
            df_data.append({
                'ID': category['id'],
                'Name': category['name'],
                'Created': category['created_at'].strftime('%Y-%m-%d %H:%M') if category['created_at'] else ''
            })
        
        return pd.DataFrame(df_data)
    
    @output
    @render.ui
    def task_notes_display():
        if not input.edit_task_id():
            return ui.div()
        
        task_id = int(input.edit_task_id())
        notes = db.get_task_notes(task_id)
        
        if not notes:
            return ui.div()
        
        note_elements = [ui.h4("Task Notes:")]
        for note in notes:
            note_elements.append(
                ui.div(
                    ui.strong(f"Added: {note['created_at'].strftime('%Y-%m-%d %H:%M')}"),
                    ui.br(),
                    note['note'],
                    style="border: 1px solid #ddd; padding: 10px; margin: 5px 0; border-radius: 5px;"
                )
            )
        
        return ui.div(*note_elements)

app = App(app_ui, server)

if __name__ == "__main__":
    app.run()
