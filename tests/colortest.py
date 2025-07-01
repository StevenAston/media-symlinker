# colortest.py
from colorama import init, Fore, Style

# init() is important for Windows compatibility
init(autoreset=True)

print("This is a test of your terminal's color support.")
print(f"This word should be {Fore.RED}red{Style.RESET_ALL}.")
print(f"This word should be {Fore.GREEN}green{Style.RESET_ALL}.")
print(f"And this word should be {Fore.CYAN}cyan{Style.RESET_ALL}.")