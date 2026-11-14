"""
Run native worker test suite using official Datasmith runtime
"""
import os
from pathlib import Path
import sys
import unittest

def main():
    os.environ['TM_VENDOR_DIR'] = r"C:\DatasmithRuntime"
    test_dir = Path("upstream_repo/tests").resolve()
    sys.path.insert(0, str(test_dir))
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Load native test cases
    for module_name in ['test_native_performance', 'test_camera_native', 'test_binary_native']:
        try:
            mod = __import__(module_name)
            suite.addTests(loader.loadTestsFromModule(mod))
        except Exception as e:
            print(f"Failed to load {module_name}: {e}")
            
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

if __name__ == "__main__":
    main()
