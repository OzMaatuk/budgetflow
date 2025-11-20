"""BudgetFlow launcher"""
import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

if __name__ == "__main__":
    # Import main module (now from src in path)
    import main as main_module
    main_module.main()
