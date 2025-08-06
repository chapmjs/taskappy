import os
from datetime import datetime
from shiny import App, render, ui, reactive
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Database configuration
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'taskapp'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'port': os.getenv('DB_PORT', '5432')
}

# Category and Status options
CATEGORIES = {
    1: "Relationship with God",
    2: "Spouse", 
    3: "Family",
    4: "Church",
    5: "Work-Education",
    6: "Community-Friends",
    7: "Hobbies-Interest"
}

STATUSES = ["Idea", "Open", "Closed"]

class DatabaseManager:
    def __init__(self):
        self.config = DATABASE_CONFIG
        self.init_database()
    
    def get_connection(self):
        try:
            conn = psycopg2.connect(**self.config)
            return conn
        except Exception as e:
            logging.error(f"Database connection error: {e}")
            return None
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        if not conn:
            return
        
        try:
            with conn.cursor() as cur:
                # Create tasks table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id SERIAL PRIMARY KEY,
                        subject VARCHAR(255) NOT NULL,
                        category INTEGER NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'Idea',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create notes table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS task_notes (
                        id SERIAL PRIMARY KEY,
                        task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
                        note TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
        finally:
            conn.close()
    
    def create_task(self, subject, category, status, note=None):
        """Create a new task with optional initial note"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cur:
                # Insert task
                cur.execute("""
                    INSERT INTO tasks (subject, category, status) 
                    VALUES (%s, %s, %s) RETURNING id
                """, (subject, category, status))
                
                task_id = cur.fetchone()[0]
                
                # Add initial note if provided
                if note and note.strip():
                    cur.execute("""
                        INSERT INTO task_notes (task_id, note) 
                        VALUES (%s, %s)
                    """, (task_id, note.strip()))
                
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Create task error: {e}")
            return False
        finally:
            conn.close()
    
    def get_all_tasks(self):
        """Get all tasks with their notes"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT t.*, 
                           STRING_AGG(tn.note, ' | ' ORDER BY tn.created_at) as notes
                    FROM tasks t
                    LEFT JOIN task_notes tn ON t.id = tn.task_id
                    GROUP BY t.id, t.subject, t.category, t.status, t.created_at, t.updated_at
                    ORDER BY t.created_at DESC
                """)
                return cur.fetchall()
        except Exception as e:
            logging.error(f"Get tasks error: {e}")
            return []
        finally:
            conn.close()
    
    def get_task_by_id(self, task_id):
        """Get a specific task by ID"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
                return cur.fetchone()
        except Exception as e:
            logging.error(f"Get task error: {e}")
            return None
        finally:
            conn.close()
    
    def get_task_notes(self, task_id):
        """Get all notes for a specific task"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM task_notes 
                    WHERE task_id = %s 
                    ORDER BY created_at DESC
                """, (task_id,))
                return cur.fetchall()
        except Exception as e:
            logging.error(f"Get task notes error: {e}")
            return []
        finally:
            conn.close()
    
    def update_task(self, task_id, subject, category, status):
        """Update a task"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE tasks 
                    SET subject = %s, category = %s, status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (subject, category, status, task_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Update task error: {e}")
            return False
        finally:
            conn.close()
    
    def add_note_to_task(self, task_id, note):
        """Add a note to an existing task"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO task_notes (task_id, note) 
                    VALUES (%s, %s)
                """, (task_id, note))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Add note error: {e}")
            return False
        finally:
            conn.close()
    
    def delete_task(self, task_id):
        """Delete a task and all its notes"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Delete task error: {e}")
            return False
        finally:
            conn.close()

# Initialize database manager
db = DatabaseManager()

# Define UI
app_ui = ui.page_fluid(
    ui.h1("Simple Task Manager"),
    
    ui.row(
        ui.column(6,
            ui.card(
                ui.card_header("Add New Task"),
                ui.input_text("task_subject", "Task Subject:", placeholder="Enter task subject"),
                ui.input_select("task_category", "Category:", 
                    choices={str(k): v for k, v in CATEGORIES.items()}),
                ui.input_select("task_status", "Status:", choices=STATUSES, selected="Idea"),
                ui.input_text_area("task_note", "Initial Note (Optional):", rows=3),
                ui.input_action_button("add_task", "Add Task", class_="btn-primary")
            )
        ),
        
        ui.column(6,
            ui.card(
                ui.card_header("Edit Task"),
                ui.input_select("edit_task_id", "Select Task to Edit:", choices={}),
                ui.input_text("edit_subject", "Subject:"),
                ui.input_select("edit_category", "Category:", 
                    choices={str(k): v for k, v in CATEGORIES.items()}),
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
    
    ui.card(
        ui.card_header("All Tasks"),
        ui.output_data_frame("tasks_table")
    ),
    
    ui.div(id="selected_task_notes", style="margin-top: 20px;"),
    ui.output_ui("task_notes_display")
)

def server(input, output, session):
    # Reactive value to trigger table refresh
    refresh_trigger = reactive.Value(0)
    
    # Add new task
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
            # Reset form
            ui.update_text("task_subject", value="")
            ui.update_text_area("task_note", value="")
            refresh_trigger.set(refresh_trigger.get() + 1)
    
    # Update task dropdown when tasks change
    @reactive.Effect
    def update_task_dropdown():
        refresh_trigger.get()  # Depend on refresh trigger
        tasks = db.get_all_tasks()
        choices = {str(task['id']): f"{task['subject']} ({CATEGORIES[task['category']]})" 
                  for task in tasks}
        ui.update_select("edit_task_id", choices=choices)
    
    # Update edit form when task is selected
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
    
    # Update task
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
            refresh_trigger.set(refresh_trigger.get() + 1)
    
    # Add note to task
    @reactive.Effect
    @reactive.event(input.add_note)
    def add_task_note():
        if not input.edit_task_id() or not input.new_note():
            return
        
        success = db.add_note_to_task(int(input.edit_task_id()), input.new_note())
        
        if success:
            ui.update_text_area("new_note", value="")
            refresh_trigger.set(refresh_trigger.get() + 1)
    
    # Delete task
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
            refresh_trigger.set(refresh_trigger.get() + 1)
    
    # Render tasks table
    @output
    @render.data_frame
    def tasks_table():
        refresh_trigger.get()  # Depend on refresh trigger
        tasks = db.get_all_tasks()
        
        if not tasks:
            return pd.DataFrame(columns=['ID', 'Subject', 'Category', 'Status', 'Created', 'Notes'])
        
        df_data = []
        for task in tasks:
            df_data.append({
                'ID': task['id'],
                'Subject': task['subject'],
                'Category': CATEGORIES[task['category']],
                'Status': task['status'],
                'Created': task['created_at'].strftime('%Y-%m-%d %H:%M') if task['created_at'] else '',
                'Notes': task['notes'][:100] + '...' if task['notes'] and len(task['notes']) > 100 else task['notes'] or ''
            })
        
        return pd.DataFrame(df_data)
    
    # Display notes for selected task
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
