"""
pyCapCut GUI - Simple Video Batch Creator
No coding required! Just fill in fields and click "Start Create"
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import threading
from pathlib import Path
from datetime import datetime
import pycapcut as cc

class CapCutGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("pyCapCut Video Creator v1.0")
        self.root.geometry("900x1000")
        self.root.resizable(True, True)
        
        # Variables
        self.sources_dir = tk.StringVar()
        self.voice_file = tk.StringVar()
        self.subtitle_file = tk.StringVar()
        self.video_duration = tk.IntVar(value=30)
        self.video_width = tk.IntVar(value=1920)
        self.video_height = tk.IntVar(value=1080)
        self.voice_volume = tk.DoubleVar(value=100)
        self.add_subtitles = tk.BooleanVar(value=True)
        self.mute_source = tk.BooleanVar(value=True)
        self.num_videos = tk.IntVar(value=10)
        self.test_mode = tk.BooleanVar(value=False)
        self.auto_open_capcut = tk.BooleanVar(value=False)
        self.total_videos_found = tk.IntVar(value=0)
        
        self.is_creating = False
        self.creation_thread = None
        
        self.setup_ui()
        self.setup_styles()
        
    def setup_styles(self):
        """Setup modern theme"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Colors
        style.configure('Title.TLabel', font=('Arial', 12, 'bold'), foreground='#1f77b4')
        style.configure('Header.TLabelframe', font=('Arial', 10, 'bold'))
        style.configure('Success.TLabel', foreground='#2ca02c')
        style.configure('Error.TLabel', foreground='#d62728')
        style.configure('Info.TLabel', foreground='#ff7f0e')
        
    def setup_ui(self):
        """Create UI elements"""
        
        # ===== MAIN CONTAINER =====
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== TITLE =====
        title = ttk.Label(
            main_frame,
            text="🎬 pyCapCut Video Creator",
            style='Title.TLabel'
        )
        title.pack(pady=10)
        
        # ===== INPUT SETTINGS =====
        input_frame = ttk.LabelFrame(
            main_frame,
            text="📁 INPUT SETTINGS",
            style='Header.TLabelframe',
            padding="10"
        )
        input_frame.pack(fill=tk.X, padx=5, pady=10)
        
        # Sources folder
        ttk.Label(input_frame, text="Source Videos Folder:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        sources_entry = ttk.Entry(
            input_frame,
            textvariable=self.sources_dir,
            width=50
        )
        sources_entry.grid(row=0, column=1, padx=5, sticky=tk.EW)
        ttk.Button(
            input_frame,
            text="📂 Browse",
            command=self.browse_sources
        ).grid(row=0, column=2, padx=5)
        self.sources_label = ttk.Label(input_frame, text="", style='Error.TLabel')
        self.sources_label.grid(row=0, column=3, sticky=tk.W)
        
        # Voice file
        ttk.Label(input_frame, text="Voice File (MP3):").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        voice_entry = ttk.Entry(
            input_frame,
            textvariable=self.voice_file,
            width=50
        )
        voice_entry.grid(row=1, column=1, padx=5, sticky=tk.EW)
        ttk.Button(
            input_frame,
            text="📂 Browse",
            command=self.browse_voice
        ).grid(row=1, column=2, padx=5)
        self.voice_label = ttk.Label(input_frame, text="", style='Error.TLabel')
        self.voice_label.grid(row=1, column=3, sticky=tk.W)
        
        # Subtitle file
        ttk.Label(input_frame, text="Subtitle File (SRT):").grid(
            row=2, column=0, sticky=tk.W, pady=5
        )
        sub_entry = ttk.Entry(
            input_frame,
            textvariable=self.subtitle_file,
            width=50
        )
        sub_entry.grid(row=2, column=1, padx=5, sticky=tk.EW)
        ttk.Button(
            input_frame,
            text="📂 Browse",
            command=self.browse_subtitle
        ).grid(row=2, column=2, padx=5)
        self.subtitle_label = ttk.Label(input_frame, text="", style='Error.TLabel')
        self.subtitle_label.grid(row=2, column=3, sticky=tk.W)
        
        input_frame.columnconfigure(1, weight=1)
        
        # ===== VIDEO SETTINGS =====
        video_frame = ttk.LabelFrame(
            main_frame,
            text="⚙️ VIDEO SETTINGS",
            style='Header.TLabelframe',
            padding="10"
        )
        video_frame.pack(fill=tk.X, padx=5, pady=10)
        
        # Duration
        ttk.Label(video_frame, text="Video Duration (seconds):").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        duration_spin = ttk.Spinbox(
            video_frame,
            from_=1,
            to=3600,
            textvariable=self.video_duration,
            width=10
        )
        duration_spin.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # Resolution
        ttk.Label(video_frame, text="Video Resolution:").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        res_frame = ttk.Frame(video_frame)
        res_frame.grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Label(res_frame, text="Width:").pack(side=tk.LEFT)
        ttk.Spinbox(
            res_frame,
            from_=640,
            to=3840,
            textvariable=self.video_width,
            width=8
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(res_frame, text="Height:").pack(side=tk.LEFT)
        ttk.Spinbox(
            res_frame,
            from_=480,
            to=2160,
            textvariable=self.video_height,
            width=8
        ).pack(side=tk.LEFT, padx=5)
        
        # Volume
        ttk.Label(video_frame, text="Voice Volume:").grid(
            row=2, column=0, sticky=tk.W, pady=5
        )
        volume_frame = ttk.Frame(video_frame)
        volume_frame.grid(row=2, column=1, sticky=tk.EW, padx=5)
        volume_scale = ttk.Scale(
            volume_frame,
            from_=0,
            to=100,
            variable=self.voice_volume,
            orient=tk.HORIZONTAL
        )
        volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.volume_label = ttk.Label(volume_frame, text="100%", width=5)
        self.volume_label.pack(side=tk.LEFT, padx=5)
        volume_scale.configure(command=self.update_volume_label)
        
        # Checkboxes
        ttk.Checkbutton(
            video_frame,
            text="✓ Add Subtitles",
            variable=self.add_subtitles
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Checkbutton(
            video_frame,
            text="✓ Mute Source Audio",
            variable=self.mute_source
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        video_frame.columnconfigure(1, weight=1)
        
        # ===== BATCH CREATION =====
        batch_frame = ttk.LabelFrame(
            main_frame,
            text="🎬 BATCH CREATION",
            style='Header.TLabelframe',
            padding="10"
        )
        batch_frame.pack(fill=tk.X, padx=5, pady=10)
        
        # Number of videos
        ttk.Label(batch_frame, text="Number of Videos to Create:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        num_frame = ttk.Frame(batch_frame)
        num_frame.grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Spinbox(
            num_frame,
            from_=1,
            to=1000,
            textvariable=self.num_videos,
            width=8
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(num_frame, text="/ Total:").pack(side=tk.LEFT)
        self.total_label = ttk.Label(num_frame, text="?", width=4)
        self.total_label.pack(side=tk.LEFT)
        ttk.Button(
            num_frame,
            text="🔍 Scan",
            command=self.scan_videos
        ).pack(side=tk.LEFT, padx=5)
        
        # Test mode
        ttk.Checkbutton(
            batch_frame,
            text="🧪 Test Mode (Create first 3 only)",
            variable=self.test_mode
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Auto-open CapCut
        ttk.Checkbutton(
            batch_frame,
            text="🎬 Auto-open CapCut after creation",
            variable=self.auto_open_capcut
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # ===== PROGRESS =====
        progress_frame = ttk.LabelFrame(
            main_frame,
            text="📊 PROGRESS",
            style='Header.TLabelframe',
            padding="10"
        )
        progress_frame.pack(fill=tk.X, padx=5, pady=10)
        
        self.progress = ttk.Progressbar(
            progress_frame,
            length=400,
            mode='determinate'
        )
        self.progress.pack(fill=tk.X, pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="Ready", style='Info.TLabel')
        self.progress_label.pack(pady=5)
        
        self.current_label = ttk.Label(progress_frame, text="Current: -", style='Info.TLabel')
        self.current_label.pack(pady=5)
        
        # ===== ACTION BUTTONS =====
        action_frame = ttk.LabelFrame(
            main_frame,
            text="🎯 ACTIONS",
            style='Header.TLabelframe',
            padding="10"
        )
        action_frame.pack(fill=tk.X, padx=5, pady=10)
        
        button_frame = ttk.Frame(action_frame)
        button_frame.pack(fill=tk.X)
        
        self.validate_btn = ttk.Button(
            button_frame,
            text="🔍 Validate",
            command=self.validate_inputs
        )
        self.validate_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.create_btn = ttk.Button(
            button_frame,
            text="▶️ Start Create",
            command=self.start_creation
        )
        self.create_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.pause_btn = ttk.Button(
            button_frame,
            text="⏸ Pause",
            command=self.pause_creation,
            state=tk.DISABLED
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Button(
            button_frame,
            text="📂 Show Folder",
            command=self.show_output_folder
        ).pack(side=tk.LEFT, padx=5, pady=5)
        
        # ===== LOG OUTPUT =====
        log_frame = ttk.LabelFrame(
            main_frame,
            text="📝 LOG OUTPUT",
            style='Header.TLabelframe',
            padding="5"
        )
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=10)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Log text
        self.log_text = tk.Text(
            log_frame,
            height=12,
            width=80,
            yscrollcommand=scrollbar.set,
            font=('Courier', 9),
            bg='#f5f5f5'
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # Configure text tags for colors
        self.log_text.tag_config('success', foreground='#2ca02c')
        self.log_text.tag_config('error', foreground='#d62728')
        self.log_text.tag_config('info', foreground='#ff7f0e')
        self.log_text.tag_config('processing', foreground='#1f77b4')
        
    def log(self, message, tag='info'):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, full_message, tag)
        self.log_text.see(tk.END)
        self.root.update()
        
    def update_volume_label(self, value):
        """Update volume percentage label"""
        self.volume_label.config(text=f"{int(float(value))}%")
        
    def browse_sources(self):
        """Browse sources folder"""
        folder = filedialog.askdirectory(title="Select Sources Folder")
        if folder:
            self.sources_dir.set(folder)
            self.check_sources()
            
    def browse_voice(self):
        """Browse voice file"""
        file = filedialog.askopenfilename(
            title="Select Voice File",
            filetypes=[("MP3 files", "*.mp3"), ("All files", "*.*")]
        )
        if file:
            self.voice_file.set(file)
            self.check_voice()
            
    def browse_subtitle(self):
        """Browse subtitle file"""
        file = filedialog.askopenfilename(
            title="Select Subtitle File",
            filetypes=[("SRT files", "*.srt"), ("All files", "*.*")]
        )
        if file:
            self.subtitle_file.set(file)
            self.check_subtitle()
            
    def check_sources(self):
        """Check if sources folder exists and has videos"""
        folder = self.sources_dir.get()
        if not folder:
            self.sources_label.config(text="⚠️ Not selected", style='Error.TLabel')
            return False
        
        if not os.path.exists(folder):
            self.sources_label.config(text="❌ Folder not found", style='Error.TLabel')
            return False
        
        videos = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]
        if not videos:
            self.sources_label.config(text="❌ No videos found", style='Error.TLabel')
            return False
        
        self.sources_label.config(text=f"✅ {len(videos)} videos", style='Success.TLabel')
        return True
        
    def check_voice(self):
        """Check if voice file exists"""
        file = self.voice_file.get()
        if not file:
            self.voice_label.config(text="⚠️ Not selected", style='Error.TLabel')
            return False
        
        if not os.path.exists(file):
            self.voice_label.config(text="❌ File not found", style='Error.TLabel')
            return False
        
        self.voice_label.config(text="✅ OK", style='Success.TLabel')
        return True
        
    def check_subtitle(self):
        """Check if subtitle file exists"""
        file = self.subtitle_file.get()
        if not file:
            self.subtitle_label.config(text="⚠️ Not selected", style='Error.TLabel')
            return False
        
        if not os.path.exists(file):
            self.subtitle_label.config(text="❌ File not found", style='Error.TLabel')
            return False
        
        self.subtitle_label.config(text="✅ OK", style='Success.TLabel')
        return True
        
    def scan_videos(self):
        """Scan and count videos in folder"""
        if not self.check_sources():
            messagebox.showerror("Error", "Sources folder not valid")
            return
        
        folder = self.sources_dir.get()
        videos = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]
        count = len(videos)
        
        self.total_videos_found.set(count)
        self.total_label.config(text=str(count))
        
        if count > 0:
            self.num_videos.set(min(count, self.num_videos.get()))
            messagebox.showinfo("Scan Complete", f"Found {count} video files")
            self.log(f"✅ Scanned {count} video files", 'success')
        else:
            messagebox.showwarning("No Videos", "No video files found in folder")
            
    def validate_inputs(self):
        """Validate all inputs"""
        self.log("Validating inputs...", 'processing')
        
        # Check sources
        if not self.check_sources():
            self.log("❌ Sources folder invalid", 'error')
            messagebox.showerror("Error", "Sources folder not valid")
            return False
        self.log("✅ Sources folder OK", 'success')
        
        # Check voice
        if not self.check_voice():
            self.log("❌ Voice file invalid", 'error')
            messagebox.showerror("Error", "Voice file not valid")
            return False
        self.log("✅ Voice file OK", 'success')
        
        # Check subtitle if enabled
        if self.add_subtitles.get():
            if not self.check_subtitle():
                self.log("❌ Subtitle file invalid", 'error')
                messagebox.showerror("Error", "Subtitle file not valid")
                return False
            self.log("✅ Subtitle file OK", 'success')
        
        # Check CapCut drafts folder
        try:
            import os.path
            # Try to find CapCut Drafts folder
            documents = str(Path.home() / "Documents")
            capcut_drafts = os.path.join(documents, "CapCut Drafts")
            if not os.path.exists(capcut_drafts):
                self.log("⚠️ CapCut Drafts folder not found. Creating...", 'info')
                os.makedirs(capcut_drafts, exist_ok=True)
            self.log("✅ CapCut Drafts folder ready", 'success')
        except Exception as e:
            self.log(f"❌ Error checking CapCut folder: {str(e)}", 'error')
            return False
        
        self.log("✅ All validations passed!", 'success')
        messagebox.showinfo("Success", "All inputs are valid!\nReady to create videos.")
        return True
        
    def start_creation(self):
        """Start video creation in background thread"""
        if not self.validate_inputs():
            return
        
        self.is_creating = True
        self.create_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.validate_btn.config(state=tk.DISABLED)
        
        # Run in separate thread
        self.creation_thread = threading.Thread(target=self.create_videos)
        self.creation_thread.start()
        
    def pause_creation(self):
        """Pause video creation"""
        self.is_creating = False
        self.pause_btn.config(state=tk.DISABLED)
        self.create_btn.config(state=tk.NORMAL, text="▶️ Resume")
        self.log("⏸ Creation paused", 'info')
        
    def create_videos(self):
        """Main video creation logic"""
        try:
            # Setup
            documents = str(Path.home() / "Documents")
            capcut_drafts = os.path.join(documents, "CapCut Drafts")
            
            draft_folder = cc.DraftFolder(capcut_drafts)
            sources_dir = self.sources_dir.get()
            voice_file = self.voice_file.get()
            subtitle_file = self.subtitle_file.get() if self.add_subtitles.get() else None
            
            # Get videos
            video_files = sorted([
                f for f in os.listdir(sources_dir)
                if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))
            ])
            
            num_to_create = self.num_videos.get()
            if self.test_mode.get():
                num_to_create = min(3, len(video_files))
                self.log("🧪 TEST MODE: Creating first 3 videos only", 'info')
            
            num_to_create = min(num_to_create, len(video_files))
            
            self.log(f"Starting creation of {num_to_create} videos...", 'processing')
            self.log(f"Duration: {self.video_duration.get()}s | Resolution: {self.video_width.get()}x{self.video_height.get()}", 'info')
            
            # Create videos
            for idx in range(num_to_create):
                if not self.is_creating:
                    self.log("⏸ Creation paused by user", 'info')
                    break
                
                video_file = video_files[idx]
                
                try:
                    # Update progress
                    progress = int((idx / num_to_create) * 100)
                    self.progress['value'] = progress
                    self.progress_label.config(
                        text=f"{idx + 1}/{num_to_create} videos created"
                    )
                    self.current_label.config(text=f"Current: auto_video_{idx + 1:03d}")
                    
                    # Create draft
                    script = draft_folder.create_draft(
                        f"auto_video_{idx + 1:03d}",
                        self.video_width.get(),
                        self.video_height.get(),
                        allow_replace=True
                    )
                    
                    # Add tracks
                    script.add_track(cc.TrackType.video, "source")
                    script.add_track(cc.TrackType.audio, "voice")
                    if self.add_subtitles.get():
                        script.add_track(cc.TrackType.text, "subtitle")
                    
                    # Add video segment
                    video_path = os.path.join(sources_dir, video_file)
                    video_seg = cc.VideoSegment(
                        video_path,
                        cc.trange("0s", f"{self.video_duration.get()}s")
                    )
                    script.add_segment(video_seg, "source")
                    self.log(f"  ├─ Added video: {video_file}", 'success')
                    
                    # Add voice segment
                    voice_seg = cc.AudioSegment(
                        voice_file,
                        cc.trange("0s", f"{self.video_duration.get()}s"),
                        volume=self.voice_volume.get() / 100
                    )
                    script.add_segment(voice_seg, "voice")
                    self.log(f"  ├─ Added voice: {int(self.voice_volume.get())}% volume", 'success')
                    
                    # Add subtitle
                    if self.add_subtitles.get() and subtitle_file:
                        script.import_srt(
                            subtitle_file,
                            track_name="subtitle",
                            time_offset="0s"
                        )
                        self.log(f"  ├─ Added subtitle", 'success')
                    
                    # Save
                    script.save()
                    self.log(f"✅ [{idx + 1}] auto_video_{idx + 1:03d} created successfully", 'success')
                    
                except Exception as e:
                    self.log(f"❌ [{idx + 1}] Error creating {video_file}: {str(e)}", 'error')
                    continue
            
            # Final progress
            self.progress['value'] = 100
            self.progress_label.config(text=f"✅ Completed: {num_to_create} videos created!")
            self.log(f"\n🎉 All done! {num_to_create} videos created successfully!", 'success')
            self.log(f"📁 Videos saved in: {capcut_drafts}", 'info')
            
            # Auto-open CapCut
            if self.auto_open_capcut.get():
                self.log("🎬 Opening CapCut...", 'info')
                try:
                    if sys.platform == 'win32':
                        os.startfile(capcut_drafts)
                except:
                    pass
            
            messagebox.showinfo("Success", f"{num_to_create} videos created successfully!\n\nOpen CapCut to review.")
            
        except Exception as e:
            self.log(f"❌ Fatal error: {str(e)}", 'error')
            messagebox.showerror("Error", f"Creation failed: {str(e)}")
        
        finally:
            self.create_btn.config(state=tk.NORMAL, text="▶️ Start Create")
            self.pause_btn.config(state=tk.DISABLED)
            self.validate_btn.config(state=tk.NORMAL)
            self.is_creating = False
            
    def show_output_folder(self):
        """Open CapCut Drafts folder"""
        try:
            documents = str(Path.home() / "Documents")
            capcut_drafts = os.path.join(documents, "CapCut Drafts")
            if sys.platform == 'win32':
                os.startfile(capcut_drafts)
            elif sys.platform == 'darwin':
                os.system(f'open "{capcut_drafts}"')
            else:
                os.system(f'xdg-open "{capcut_drafts}"')
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {str(e)}")

def main():
    root = tk.Tk()
    gui = CapCutGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()