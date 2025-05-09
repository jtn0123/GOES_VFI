#!/usr/bin/env python3
"""Test script for VfiWorker initialization."""

import os
import sys
import pathlib
import tempfile
from pathlib import Path
from datetime import datetime

# Add the project directory to the Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

try:
    # Import VfiWorker
    from goesvfi.pipeline.run_vfi import VfiWorker
    
    # We'll need Qt for the signals
    from PyQt6.QtCore import QObject, pyqtSlot
    
    class TestReceiver(QObject):
        """Test class to receive signals from VfiWorker."""
        
        def __init__(self):
            super().__init__()
            self.progress_received = False
            self.finished_received = False
            self.error_received = False
            
        @pyqtSlot(int, int, float)
        def on_progress(self, current, total, elapsed):
            print(f"Progress: {current}/{total} ({elapsed:.2f}s)")
            self.progress_received = True
            
        @pyqtSlot(pathlib.Path)
        def on_finished(self, output_path):
            print(f"Finished: {output_path}")
            self.finished_received = True
            
        @pyqtSlot(str)
        def on_error(self, error_message):
            print(f"Error: {error_message}")
            self.error_received = True
    
    def test_vfi_worker_init():
        """Test VfiWorker initialization."""
        print("Testing VfiWorker initialization...")
        
        # Create test paths
        test_in_dir = Path("/tmp/test_in_dir")
        test_out_file = Path("/tmp/test_output.mp4")
        
        # Create temporary directory for Sanchez
        sanchez_temp_dir = Path(tempfile.mkdtemp(prefix="sanchez_test_"))
        
        # Create arguments with the exact names expected by VfiWorker.__init__
        required_args = {
            'in_dir': test_in_dir,
            'out_file_path': test_out_file,
            'fps': 30,
            'mid_count': 3,
            'max_workers': 4,
            'encoder': 'RIFE',
            # FFmpeg settings
            'use_preset_optimal': False,
            'use_ffmpeg_interp': False,
            'filter_preset': 'slow',
            'mi_mode': 'mci',
            'mc_mode': 'obmc',
            'me_mode': 'bidir',
            'me_algo': '',
            'search_param': 96,
            'scd_mode': 'fdiff',
            'scd_threshold': None,
            'minter_mb_size': None,
            'minter_vsbmc': 0,
            # Unsharp settings
            'apply_unsharp': False,
            'unsharp_lx': 3,
            'unsharp_ly': 3,
            'unsharp_la': 1.0,
            'unsharp_cx': 0.5,
            'unsharp_cy': 0.5,
            'unsharp_ca': 0.0,
            # Quality settings - Use names from VfiWorker
            'crf': 18,
            'bitrate_kbps': 7000,
            'bufsize_kb': 14000,
            'pix_fmt': 'yuv420p',
            # Other required args
            'skip_model': False,
            'crop_rect': None,
            'debug_mode': True,
            # RIFE settings with correct parameter names
            'rife_tile_enable': True,
            'rife_tile_size': 384,
            'rife_uhd_mode': False,
            'rife_thread_spec': '0:0:0:0',
            'rife_tta_spatial': False,
            'rife_tta_temporal': False,
            'model_key': 'rife-v4.6',
            # Sanchez settings with correct parameter names
            'false_colour': False,  # Renamed from sanchez_enable
            'res_km': 4,  # Renamed and changed type from sanchez_resolution_km
            # Sanchez GUI temp dir
            'sanchez_gui_temp_dir': sanchez_temp_dir
        }
        
        try:
            # Create VfiWorker instance
            worker = VfiWorker(**required_args)
            print("VfiWorker initialized successfully.")
            
            # Connect signals to test receiver
            receiver = TestReceiver()
            worker.progress.connect(receiver.on_progress)
            worker.finished.connect(receiver.on_finished)
            worker.error.connect(receiver.on_error)
            print("Signals connected successfully.")
            
            # Don't actually start the worker as it would try to process files
            # worker.start()
            
            return True
        except Exception as e:
            print(f"Error initializing VfiWorker: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    if __name__ == "__main__":
        result = test_vfi_worker_init()
        sys.exit(0 if result else 1)
            
except ImportError as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)