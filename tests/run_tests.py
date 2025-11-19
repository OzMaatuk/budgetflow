"""Test runner script."""
import unittest
import sys
from pathlib import Path

# Add parent directory to path so budgetflow can be imported as a package
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

if __name__ == "__main__":
    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(start_dir, pattern="test_*.py")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)
