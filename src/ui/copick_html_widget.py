from typing import Optional
from Qt.QtCore import QObject, QRunnable, QThreadPool, QUrl
from Qt.QtWidgets import QApplication
from Qt.QtGui import QDesktopServices
from chimerax.ui.widgets import ChimeraXHtmlView


class DataLoadWorker(QRunnable):
    """Worker for loading run data in background thread"""
    
    def __init__(self, widget, run, data_type):
        super().__init__()
        self.widget = widget
        self.run = run
        self.data_type = data_type
        self.setAutoDelete(True)
    
    def run(self):
        """Load data and update widget via signals"""
        try:
            if self.data_type == "voxel_spacings":
                # Load voxel spacings (lazy loaded)
                data = list(self.run.voxel_spacings)
                QApplication.instance().postEvent(
                    self.widget, 
                    DataLoadedEvent(self.data_type, data)
                )
            elif self.data_type == "tomograms":
                # Load all tomograms across all voxel spacings
                tomograms = []
                for vs in self.run.voxel_spacings:
                    tomograms.extend(list(vs.tomograms))
                QApplication.instance().postEvent(
                    self.widget, 
                    DataLoadedEvent(self.data_type, tomograms)
                )
            elif self.data_type == "picks":
                # Load picks
                data = list(self.run.picks)
                QApplication.instance().postEvent(
                    self.widget, 
                    DataLoadedEvent(self.data_type, data)
                )
            elif self.data_type == "meshes":
                # Load meshes
                data = list(self.run.meshes)
                QApplication.instance().postEvent(
                    self.widget, 
                    DataLoadedEvent(self.data_type, data)
                )
            elif self.data_type == "segmentations":
                # Load segmentations
                data = list(self.run.segmentations)
                QApplication.instance().postEvent(
                    self.widget, 
                    DataLoadedEvent(self.data_type, data)
                )
        except Exception as e:
            # Send error event
            QApplication.instance().postEvent(
                self.widget, 
                DataLoadedEvent(self.data_type, None, str(e))
            )


from Qt.QtCore import QEvent

class DataLoadedEvent(QEvent):
    """Custom event for data loading completion"""
    EventType = QEvent.Type(QEvent.registerEventType())
    
    def __init__(self, data_type, data, error=None):
        super().__init__(self.EventType)
        self.data_type = data_type
        self.data = data
        self.error = error


class CopickHtmlWidget(ChimeraXHtmlView):
    """HTML-based widget for displaying copick run information with async loading"""
    
    def __init__(self, session, parent: Optional[QObject] = None, **kw):
        super().__init__(session, parent, **kw)
        self.session = session
        self.current_run_name = None
        self.current_run = None
        self._is_destroyed = False
        self._thread_pool = QThreadPool()
        self._thread_pool.setMaxThreadCount(4)  # Limit concurrent threads
        self._loading_states = {}  # Track what's currently loading
        self._loaded_data = {}  # Cache loaded data
        
        # Register for app quit trigger to ensure proper cleanup (like FileHistory widget)
        if hasattr(session, 'triggers'):
            session.triggers.add_handler('app quit', self._app_quit)
        
        self.update_html()
    
    def _app_quit(self, *args):
        """Handle app quit trigger to ensure proper cleanup (like FileHistory widget)"""
        if not self._is_destroyed:
            self.deleteLater()
    
    def delete(self):
        """Properly clean up the widget to avoid WebEngine warnings"""
        if self._is_destroyed:
            return
        
        self._is_destroyed = True
        
        try:
            # Stop thread pool
            if hasattr(self, '_thread_pool'):
                self._thread_pool.clear()
                self._thread_pool.waitForDone(3000)  # Wait up to 3 seconds
            
            # Let ChimeraXHtmlView handle proper WebEngine cleanup
            super().delete()
        except Exception:
            # Silently handle any cleanup errors
            pass
    
    def set_run_name(self, run_name: str):
        """Set the current run name and update the display"""
        self.current_run_name = run_name
        self.current_run = None  # Will be set by set_run()
        self.update_html()
    
    def set_run(self, run):
        """Set the current run object and start async loading"""
        if self._is_destroyed:
            return
            
        self.current_run = run
        if run:
            self.current_run_name = run.name
            # Clear previous data and loading states
            self._loaded_data.clear()
            self._loading_states.clear()
            
            # Start async loading of all data types
            self._start_async_loading()
        else:
            self.current_run_name = None
            self._loaded_data.clear()
            self._loading_states.clear()
        
        self.update_html()
    
    def _start_async_loading(self):
        """Start asynchronous loading of all run data"""
        if not self.current_run or self._is_destroyed:
            return
        
        data_types = ["voxel_spacings", "tomograms", "picks", "meshes", "segmentations"]
        
        for data_type in data_types:
            if data_type not in self._loading_states:
                self._loading_states[data_type] = "loading"
                worker = DataLoadWorker(self, self.current_run, data_type)
                self._thread_pool.start(worker)
    
    def event(self, event):
        """Handle custom events from worker threads"""
        if event.type() == DataLoadedEvent.EventType:
            self._handle_data_loaded(event)
            return True
        return super().event(event)
    
    def _handle_data_loaded(self, event):
        """Handle data loading completion"""
        if self._is_destroyed:
            return
            
        data_type = event.data_type
        
        if event.error:
            self._loading_states[data_type] = f"error: {event.error}"
        else:
            self._loading_states[data_type] = "loaded"
            self._loaded_data[data_type] = event.data
        
        # Update the HTML to show new data
        self.update_html()
    
    def update_html(self):
        """Update the HTML content"""
        html = self.generate_html()
        self.setHtml(html)
        
        # Note: ChimeraX's HTML widget may have limited external link support
        # The target="_blank" attribute in the HTML should still work in most cases
    
    def _handle_link_click(self, url):
        """Handle link clicks to open external URLs in system browser"""
        try:
            # Open the URL in the system default browser
            QDesktopServices.openUrl(QUrl(url))
        except Exception:
            # Silently handle any errors opening the URL
            pass
    
    def generate_html(self):
        """Generate HTML content for the widget with loading states and data"""
        run_display = self.current_run_name or "No run selected"
        
        # Generate content sections
        content_sections = ""
        if self.current_run:
            content_sections = self._generate_data_sections()
        
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
            min-height: 100vh;
            box-sizing: border-box;
        }}
        
        .run-container {{
            max-width: 800px;
            margin: 0 auto;
            padding: 30px;
            border-radius: 12px;
            background: var(--panel-background);
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }}
        
        .run-header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        
        .run-title {{
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 10px;
            color: var(--text-color);
        }}
        
        .run-name {{
            font-size: 28px;
            font-weight: 700;
            color: var(--accent-color, #007AFF);
            margin-bottom: 20px;
            word-break: break-word;
        }}
        
        .data-section {{
            margin-bottom: 25px;
            padding: 20px;
            background: var(--secondary-background);
            border-radius: 8px;
            border-left: 4px solid var(--accent-color, #007AFF);
        }}
        
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
            color: var(--text-color);
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .loading-spinner {{
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid var(--border-color);
            border-radius: 50%;
            border-top-color: var(--accent-color, #007AFF);
            animation: spin 1s ease-in-out infinite;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        .status-indicator {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }}
        
        .status-loading {{
            background: #FFF3CD;
            color: #856404;
        }}
        
        .status-loaded {{
            background: #D4EDDA;
            color: #155724;
        }}
        
        .status-error {{
            background: #F8D7DA;
            color: #721C24;
        }}
        
        .data-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        
        .data-item {{
            padding: 8px 12px;
            margin-bottom: 6px;
            background: var(--background-color);
            border-radius: 4px;
            border: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .item-name {{
            font-weight: 500;
        }}
        
        .item-details {{
            font-size: 12px;
            color: var(--secondary-text-color);
        }}
        
        .empty-state {{
            text-align: center;
            padding: 20px;
            color: var(--secondary-text-color);
            font-style: italic;
        }}
        
        .switch-hint {{
            text-align: center;
            font-size: 14px;
            color: var(--secondary-text-color);
            margin-top: 30px;
            padding: 12px;
            background: var(--secondary-background);
            border-radius: 6px;
        }}
        
        /* Voxel spacing and tomogram nesting styles */
        .voxel-spacing-section {{
            margin-bottom: 15px;
            padding: 12px;
            background: var(--background-color);
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }}
        
        .voxel-spacing-title {{
            margin: 0 0 8px 0;
            font-size: 14px;
            font-weight: 600;
            color: var(--text-color);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .tomogram-list {{
            padding-left: 15px;
        }}
        
        .tomogram-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 4px 8px;
            margin-bottom: 4px;
            background: var(--secondary-background);
            border-radius: 4px;
            font-size: 13px;
        }}
        
        .tomogram-icon {{
            font-size: 12px;
        }}
        
        .tomogram-name {{
            flex: 1;
            color: var(--text-color);
        }}
        
        /* Annotation group styles */
        .annotations-group {{
            border-left: 4px solid #28a745;
        }}
        
        .annotations-container {{
            padding-left: 15px;
        }}
        
        .annotation-subsection {{
            margin-bottom: 15px;
            padding: 8px;
            background: var(--background-color);
            border-radius: 4px;
            border: 1px solid var(--border-color);
        }}
        
        .annotation-title {{
            margin: 0 0 8px 0;
            font-size: 14px;
            font-weight: 600;
            color: var(--text-color);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .annotation-content {{
            padding-left: 10px;
        }}
        
        .annotation-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 6px 8px;
            margin-bottom: 4px;
            background: var(--secondary-background);
            border-radius: 4px;
            font-size: 13px;
        }}
        
        .annotation-info {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }}
        
        .annotation-name {{
            font-weight: 500;
            color: var(--text-color);
        }}
        
        .annotation-details {{
            font-size: 11px;
            color: var(--secondary-text-color);
        }}
        
        .annotation-count {{
            font-size: 12px;
            color: var(--secondary-text-color);
            font-weight: normal;
        }}
        
        .annotation-error {{
            color: #dc3545;
        }}
        
        .annotation-pending {{
            color: var(--secondary-text-color);
        }}
        
        /* CryoET Data Portal link styles */
        .portal-link {{
            color: #007AFF;
            text-decoration: none;
            font-size: 11px;
            font-weight: 500;
            padding: 2px 6px;
            border-radius: 3px;
            background: rgba(0, 122, 255, 0.1);
            transition: all 0.2s ease;
        }}
        
        .portal-link:hover {{
            background: rgba(0, 122, 255, 0.2);
            text-decoration: none;
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
        
        /* Light mode variables - adjust loading/status colors for light mode */
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
            .status-loading {{
                background: #FFF3CD;
                color: #856404;
            }}
            .status-loaded {{
                background: #D4EDDA;
                color: #155724;
            }}
            .status-error {{
                background: #F8D7DA;
                color: #721C24;
            }}
        }}
        </style>
        </head>
        <body>
        <div class="run-container">
            <div class="run-header">
                <div class="run-title">📊 Copick Run Details</div>
                <div class="run-name">{run_display}</div>
            </div>
            
            {content_sections}
            
            <div class="switch-hint">
                💡 Use the overlay button on the tree widget to switch between OpenGL and info views
            </div>
        </div>
        </body>
        </html>
        """
    
    def _generate_data_sections(self):
        """Generate HTML sections for each data type with proper nesting and grouping"""
        if not self.current_run:
            return '<div class="empty-state">Select a run from the copick tree to view its contents.</div>'
        
        sections = []
        
        # Generate voxel spacings section with nested tomograms
        sections.append(self._generate_voxel_spacings_section())
        
        # Generate annotations group (picks, meshes, segmentations)
        sections.append(self._generate_annotations_group())
        
        return "\n".join(sections)
    
    def _generate_voxel_spacings_section(self):
        """Generate the voxel spacings section with nested tomograms"""
        voxel_status = self._loading_states.get("voxel_spacings", "not_started")
        tomo_status = self._loading_states.get("tomograms", "not_started")
        
        # Status indicator for voxel spacings
        if voxel_status == "loading":
            status_html = '<span class="loading-spinner"></span><span class="status-indicator status-loading">Loading voxel spacings...</span>'
        elif voxel_status == "loaded":
            vs_count = len(self._loaded_data.get("voxel_spacings", []))
            tomo_count = len(self._loaded_data.get("tomograms", []))
            status_html = f'<span class="status-indicator status-loaded">✓ {vs_count} voxel spacings, {tomo_count} tomograms</span>'
        elif voxel_status.startswith("error:"):
            error_msg = voxel_status[6:]
            status_html = f'<span class="status-indicator status-error">✗ Error: {error_msg}</span>'
        else:
            status_html = '<span class="status-indicator">Pending...</span>'
        
        # Content
        content_html = ""
        if voxel_status == "loaded" and "voxel_spacings" in self._loaded_data:
            voxel_spacings = self._loaded_data["voxel_spacings"]
            tomograms = self._loaded_data.get("tomograms", [])
            
            if voxel_spacings:
                content_html = self._generate_nested_voxel_tomogram_list(voxel_spacings, tomograms)
            else:
                content_html = '<div class="empty-state">No voxel spacings found</div>'
        elif voxel_status.startswith("error:"):
            content_html = '<div class="empty-state">Failed to load voxel spacings</div>'
        elif voxel_status == "loading":
            content_html = '<div class="empty-state">Loading voxel spacings...</div>'
        else:
            content_html = '<div class="empty-state">Not loaded yet</div>'
        
        return f"""
        <div class="data-section">
            <div class="section-title">
                📏 Voxel Spacings & Tomograms
                {status_html}
            </div>
            {content_html}
        </div>
        """
    
    def _generate_annotations_group(self):
        """Generate the annotations group section"""
        # Check if any annotation data is loaded
        picks_status = self._loading_states.get("picks", "not_started")
        meshes_status = self._loading_states.get("meshes", "not_started")
        seg_status = self._loading_states.get("segmentations", "not_started")
        
        # Count loaded items
        picks_count = len(self._loaded_data.get("picks", []))
        meshes_count = len(self._loaded_data.get("meshes", []))
        seg_count = len(self._loaded_data.get("segmentations", []))
        total_count = picks_count + meshes_count + seg_count
        
        # Overall status
        all_loaded = all(status == "loaded" for status in [picks_status, meshes_status, seg_status])
        any_loading = any(status == "loading" for status in [picks_status, meshes_status, seg_status])
        any_error = any(status.startswith("error:") for status in [picks_status, meshes_status, seg_status])
        
        if any_loading:
            status_html = '<span class="loading-spinner"></span><span class="status-indicator status-loading">Loading annotations...</span>'
        elif all_loaded:
            status_html = f'<span class="status-indicator status-loaded">✓ {total_count} annotations</span>'
        elif any_error:
            status_html = '<span class="status-indicator status-error">✗ Some errors loading annotations</span>'
        else:
            status_html = '<span class="status-indicator">Pending...</span>'
        
        # Generate content for each annotation type
        annotations_content = []
        
        # Picks subsection
        annotations_content.append(self._generate_annotation_subsection("picks", "📍 Picks", picks_status))
        
        # Meshes subsection  
        annotations_content.append(self._generate_annotation_subsection("meshes", "🕸 Meshes", meshes_status))
        
        # Segmentations subsection
        annotations_content.append(self._generate_annotation_subsection("segmentations", "🖌 Segmentations", seg_status))
        
        return f"""
        <div class="data-section annotations-group">
            <div class="section-title">
                📋 Annotations
                {status_html}
            </div>
            <div class="annotations-container">
                {"".join(annotations_content)}
            </div>
        </div>
        """
    
    def _generate_section(self, data_type, title, icon):
        """Generate HTML for a single data section"""
        status = self._loading_states.get(data_type, "not_started")
        
        # Status indicator
        if status == "loading":
            status_html = '<span class="loading-spinner"></span><span class="status-indicator status-loading">Loading...</span>'
        elif status == "loaded":
            count = len(self._loaded_data.get(data_type, []))
            status_html = f'<span class="status-indicator status-loaded">✓ Loaded ({count} items)</span>'
        elif status.startswith("error:"):
            error_msg = status[6:]  # Remove "error:" prefix
            status_html = f'<span class="status-indicator status-error">✗ Error: {error_msg}</span>'
        else:
            status_html = '<span class="status-indicator">Pending...</span>'
        
        # Content
        content_html = ""
        if status == "loaded" and data_type in self._loaded_data:
            data = self._loaded_data[data_type]
            if data:
                content_html = self._generate_data_list(data_type, data)
            else:
                content_html = '<div class="empty-state">No items found</div>'
        elif status.startswith("error:"):
            content_html = '<div class="empty-state">Failed to load data</div>'
        elif status == "loading":
            content_html = '<div class="empty-state">Loading data...</div>'
        else:
            content_html = '<div class="empty-state">Not loaded yet</div>'
        
        return f"""
        <div class="data-section">
            <div class="section-title">
                {icon} {title}
                {status_html}
            </div>
            {content_html}
        </div>
        """
    
    def _generate_nested_voxel_tomogram_list(self, voxel_spacings, tomograms):
        """Generate HTML for nested voxel spacings with their tomograms"""
        if not voxel_spacings:
            return '<div class="empty-state">No voxel spacings found</div>'
        
        # Create a mapping of voxel spacings to their tomograms
        voxel_to_tomos = {}
        for vs in voxel_spacings:
            voxel_to_tomos[vs.voxel_size] = []
            
        # Group tomograms by voxel spacing
        for tomo in tomograms:
            try:
                vs_size = tomo.voxel_spacing.voxel_size
                if vs_size in voxel_to_tomos:
                    voxel_to_tomos[vs_size].append(tomo)
            except:
                pass  # Skip tomograms with invalid voxel spacing
        
        sections_html = []
        for vs in voxel_spacings:
            vs_size = vs.voxel_size
            vs_tomograms = voxel_to_tomos.get(vs_size, [])
            
            # Generate link if this is a CryoET Data Portal project
            link_html = self._generate_cryoet_link(vs)
            
            # Voxel spacing header
            sections_html.append(f"""
            <div class="voxel-spacing-section">
                <h4 class="voxel-spacing-title">
                    📏 Voxel Spacing {vs_size:.2f}Å
                    {link_html}
                </h4>
                <div class="tomogram-list">
            """)
            
            # Add tomograms for this voxel spacing
            if vs_tomograms:
                for tomo in vs_tomograms:
                    try:
                        tomo_link = self._generate_cryoet_link(tomo)
                        sections_html.append(f"""
                        <div class="tomogram-item">
                            <span class="tomogram-icon">🧊</span>
                            <span class="tomogram-name">{tomo.tomo_type}</span>
                            {tomo_link}
                        </div>
                        """)
                    except Exception as e:
                        sections_html.append(f"""
                        <div class="tomogram-item">
                            <span class="tomogram-icon">🧊</span>
                            <span class="tomogram-name">Error loading tomogram</span>
                        </div>
                        """)
            else:
                sections_html.append('<div class="empty-state">No tomograms found</div>')
                
            sections_html.append('</div></div>')
        
        return ''.join(sections_html)
    
    def _generate_annotation_subsection(self, data_type, title, status):
        """Generate HTML for an annotation subsection (picks, meshes, segmentations)"""
        # Status indicator
        if status == "loading":
            status_html = '<span class="loading-spinner"></span>'
        elif status == "loaded":
            count = len(self._loaded_data.get(data_type, []))
            status_html = f'<span class="annotation-count">({count})</span>'
        elif status.startswith("error:"):
            status_html = '<span class="annotation-error">⚠️</span>'
        else:
            status_html = '<span class="annotation-pending">⏳</span>'
        
        # Content
        content_html = ""
        if status == "loaded" and data_type in self._loaded_data:
            data = self._loaded_data[data_type]
            if data:
                content_html = self._generate_annotation_items(data_type, data)
            else:
                content_html = '<div class="empty-state">No items found</div>'
        elif status.startswith("error:"):
            content_html = '<div class="empty-state">Failed to load data</div>'
        elif status == "loading":
            content_html = '<div class="empty-state">Loading...</div>'
        else:
            content_html = '<div class="empty-state">Not loaded yet</div>'
        
        return f"""
        <div class="annotation-subsection">
            <h4 class="annotation-title">
                {title}
                {status_html}
            </h4>
            <div class="annotation-content">
                {content_html}
            </div>
        </div>
        """
    
    def _generate_annotation_items(self, data_type, data):
        """Generate HTML for annotation items (picks, meshes, segmentations)"""
        if not data:
            return '<div class="empty-state">No items found</div>'
        
        items_html = []
        
        # Show all items, not just first 10
        for item in data:
            try:
                if data_type == "picks":
                    name = f"📍 {item.pickable_object_name}"
                    try:
                        point_count = len(item.points) if hasattr(item, 'points') else 'N/A'
                    except:
                        point_count = 'N/A'
                    details = f"User: {item.user_id} | Session: {item.session_id} | Points: {point_count}"
                    link_html = self._generate_cryoet_link(item)
                elif data_type == "meshes":
                    name = f"🕸 {item.pickable_object_name}"
                    details = f"User: {item.user_id} | Session: {item.session_id}"
                    link_html = self._generate_cryoet_link(item)
                elif data_type == "segmentations":
                    seg_name = getattr(item, 'name', item.pickable_object_name if hasattr(item, 'pickable_object_name') else 'Unknown')
                    name = f"🖌 {seg_name}"
                    details = f"User: {item.user_id} | Session: {item.session_id}"
                    link_html = self._generate_cryoet_link(item)
                else:
                    name = str(item)
                    details = ""
                    link_html = ""
                
                items_html.append(f"""
                <div class="annotation-item">
                    <div class="annotation-info">
                        <span class="annotation-name">{name}</span>
                        <span class="annotation-details">{details}</span>
                    </div>
                    {link_html}
                </div>
                """)
            except Exception as e:
                # Fallback for any attribute access errors
                name = f"{data_type.rstrip('s').title()} (error displaying)"
                details = f"Error: {str(e)[:50]}..."
                items_html.append(f"""
                <div class="annotation-item">
                    <div class="annotation-info">
                        <span class="annotation-name">{name}</span>
                        <span class="annotation-details">{details}</span>
                    </div>
                </div>
                """)
        
        return ''.join(items_html)
    
    def _generate_cryoet_link(self, item):
        """Generate CryoET Data Portal link for an item if applicable"""
        try:
            # Import here to avoid circular imports
            from copick.impl.cryoet_data_portal import CopickRunCDP, CopickTomogramCDP, CopickPicksCDP, CopickSegmentationCDP
            
            # Check if this is a CryoET Data Portal project
            if hasattr(item, 'run') and isinstance(item.run, CopickRunCDP):
                run_id = item.run.portal_run_id
                
                if hasattr(item, 'meta') and hasattr(item.meta, 'portal_tomo_id'):
                    # Tomogram link
                    tomo_id = item.meta.portal_tomo_id
                    return f'<a href="https://cryoetdataportal.czscience.com/runs/{run_id}?table-tab=Tomograms" target="_blank" class="portal-link">🌐 Portal</a>'
                elif hasattr(item, 'meta') and hasattr(item.meta, 'portal_annotation_id'):
                    # Annotation link (picks, segmentations)
                    annotation_id = item.meta.portal_annotation_id
                    return f'<a href="https://cryoetdataportal.czscience.com/runs/{run_id}?table-tab=Annotations" target="_blank" class="portal-link">🌐 Portal</a>'
                elif hasattr(item, 'voxel_spacing') and hasattr(item.voxel_spacing, 'run') and isinstance(item.voxel_spacing.run, CopickRunCDP):
                    # Voxel spacing or tomogram via voxel spacing
                    run_id = item.voxel_spacing.run.portal_run_id
                    return f'<a href="https://cryoetdataportal.czscience.com/runs/{run_id}" target="_blank" class="portal-link">🌐 Portal</a>'
                else:
                    # General run link
                    return f'<a href="https://cryoetdataportal.czscience.com/runs/{run_id}" target="_blank" class="portal-link">🌐 Portal</a>'
            
            return ""
        except Exception:
            return ""
    
    def _generate_data_list(self, data_type, data):
        """Generate HTML list for data items (legacy method, kept for compatibility)"""
        if not data:
            return '<div class="empty-state">No items found</div>'
        
        items_html = []
        
        # Show all items, not just first 10
        for item in data:
            try:
                if data_type == "voxel_spacings":
                    name = f"Voxel Spacing {item.voxel_size:.2f}Å"
                    tomo_count = len(item.tomograms) if hasattr(item, 'tomograms') else 'N/A'
                    details = f"Voxel size: {item.voxel_size:.2f}Å | Tomograms: {tomo_count}"
                elif data_type == "tomograms":
                    name = f"Tomogram: {item.tomo_type}"
                    details = f"Voxel spacing: {item.voxel_spacing.voxel_size:.2f}Å"
                elif data_type == "picks":
                    name = f"{item.pickable_object_name}"
                    try:
                        point_count = len(item.points) if hasattr(item, 'points') else 'N/A'
                    except:
                        point_count = 'N/A'
                    details = f"User: {item.user_id} | Session: {item.session_id} | Points: {point_count}"
                elif data_type == "meshes":
                    name = f"{item.pickable_object_name}"
                    details = f"User: {item.user_id} | Session: {item.session_id}"
                elif data_type == "segmentations":
                    seg_name = getattr(item, 'name', item.pickable_object_name if hasattr(item, 'pickable_object_name') else 'Unknown')
                    name = f"{seg_name}"
                    details = f"User: {item.user_id} | Session: {item.session_id}"
                else:
                    name = str(item)
                    details = ""
            except Exception as e:
                # Fallback for any attribute access errors
                name = f"{data_type.rstrip('s').title()} (error displaying)"
                details = f"Error: {str(e)[:50]}..."
            
            items_html.append(f"""
            <li class="data-item">
                <span class="item-name">{name}</span>
                <span class="item-details">{details}</span>
            </li>
            """)
        
        return f'<ul class="data-list">{"".join(items_html)}</ul>'