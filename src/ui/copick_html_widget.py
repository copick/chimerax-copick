from typing import Optional
from Qt.QtCore import QObject
from chimerax.ui.widgets import ChimeraXHtmlView


class CopickHtmlWidget(ChimeraXHtmlView):
    """HTML-based widget for displaying copick run information"""
    
    def __init__(self, session, parent: Optional[QObject] = None, **kw):
        super().__init__(session, parent, **kw)
        self.session = session
        self.current_run_name = None
        self._is_destroyed = False
        self.update_html()
    
    def delete(self):
        """Properly clean up the widget to avoid WebEngine warnings"""
        if self._is_destroyed:
            return
        
        self._is_destroyed = True
        
        try:
            # Stop any loading and clear the page
            self.stop()
            self.setHtml("")
            
            # Explicitly delete the page to avoid WebEngine warnings
            page = self.page()
            if page:
                page.deleteLater()
                
            # Call parent cleanup
            super().delete()
        except Exception:
            # Silently handle any cleanup errors
            pass
    
    def closeEvent(self, event):
        """Handle close event to ensure proper cleanup"""
        self.delete()
        super().closeEvent(event)
    
    def __del__(self):
        """Destructor to ensure cleanup if delete() wasn't called"""
        if not self._is_destroyed:
            try:
                self.delete()
            except:
                pass
    
    def set_run_name(self, run_name: str):
        """Set the current run name and update the display"""
        self.current_run_name = run_name
        self.update_html()
    
    def update_html(self):
        """Update the HTML content"""
        html = self.generate_html()
        self.setHtml(html)
    
    def generate_html(self):
        """Generate HTML content for the widget"""
        run_display = self.current_run_name or "No run selected"
        
        return f"""
        <html>
        <head>
        <style>
        {self.session.ui.dark_css()}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: var(--background-color);
            color: var(--text-color);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            box-sizing: border-box;
        }}
        
        .run-container {{
            text-align: center;
            padding: 40px;
            border-radius: 12px;
            background: var(--panel-background);
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            max-width: 600px;
            width: 100%;
        }}
        
        .run-title {{
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 20px;
            color: var(--text-color);
        }}
        
        .run-name {{
            font-size: 36px;
            font-weight: 700;
            color: var(--accent-color, #007AFF);
            margin-bottom: 20px;
            word-break: break-word;
        }}
        
        .run-description {{
            font-size: 16px;
            color: var(--secondary-text-color);
            line-height: 1.5;
            margin-bottom: 30px;
        }}
        
        .copick-logo {{
            font-size: 48px;
            margin-bottom: 30px;
            opacity: 0.8;
        }}
        
        .switch-hint {{
            font-size: 14px;
            color: var(--secondary-text-color);
            margin-top: 20px;
            padding: 12px;
            background: var(--secondary-background);
            border-radius: 6px;
            border-left: 4px solid var(--accent-color, #007AFF);
        }}
        
        /* Dark mode variables */
        :root {{
            --background-color: #1a1a1a;
            --text-color: #ffffff;
            --secondary-text-color: #999999;
            --panel-background: #2d2d2d;
            --secondary-background: #3d3d3d;
            --border-color: #444444;
            --accent-color: #007AFF;
        }}
        
        /* Light mode variables */
        @media (prefers-color-scheme: light) {{
            :root {{
                --background-color: #ffffff;
                --text-color: #000000;
                --secondary-text-color: #666666;
                --panel-background: #f8f8f8;
                --secondary-background: #f0f0f0;
                --border-color: #dddddd;
                --accent-color: #007AFF;
            }}
        }}
        </style>
        </head>
        <body>
        <div class="run-container">
            <div class="copick-logo">📊</div>
            <div class="run-title">Current Copick Run</div>
            <div class="run-name">{run_display}</div>
            <div class="run-description">
                {'This is the currently selected run from the copick tree. Switch between the OpenGL viewport and this information view using the toggle button.' if self.current_run_name else 'Select a run from the copick tree to display information about it here.'}
            </div>
            <div class="switch-hint">
                💡 Use the overlay button on the tree widget to switch between OpenGL and info views
            </div>
        </div>
        </body>
        </html>
        """