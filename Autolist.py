import pyautogui
import time
from datetime import datetime
import keyboard

# === Step 1: Focus window on monitor 1 ===
monitor_width = 1920
monitor_height = 1080
monitor_1_x = 0
monitor_1_y = monitor_height // 2

pyautogui.moveTo(monitor_1_x + monitor_width // 2, monitor_1_y)
pyautogui.click()
time.sleep(0.3)

# === Step 2: Press Windows Key and Type 'manager' ===
pyautogui.press('win')
time.sleep(0.2)
pyautogui.write('manager', interval=0.05)
pyautogui.press('enter')

# === Step 3: Wait for the window to load ===
time.sleep(4)

# === Step 4: Press Alt, R, I, D ===
pyautogui.press('alt')
time.sleep(0.1)
pyautogui.press('r')
time.sleep(0.1)
pyautogui.press('i')
time.sleep(0.1)
pyautogui.press('d')
time.sleep(0.4)

# === Step 5: Tab twice, then 13 more times ===
for _ in range(13):
    pyautogui.press('tab')
    time.sleep(0.01)

# === Step 6: Type today's date twice ===
today = datetime.now().strftime("%m/%d/%Y")
pyautogui.write(today)
pyautogui.press('tab')
pyautogui.write(today)
pyautogui.press('enter')

pyautogui.press('alt')
time.sleep(0.1)
pyautogui.press('f')
time.sleep(0.1)
pyautogui.press('d')
time.sleep(0.1)
pyautogui.press('enter')
time.sleep(0.1)
pyautogui.press('enter')
time.sleep(2)

# === Hold DOWN for exactly 4 seconds using real-time loop ===
start_time = time.time()
while time.time() - start_time < 4:
    pyautogui.press('down')




# === Step 8: Final Enter ===
pyautogui.press('enter')

time.sleep(10)
pyautogui.press('alt')
time.sleep(0.1)
pyautogui.press('f')
time.sleep(0.1)
pyautogui.press('p')
time.sleep(0.1)
pyautogui.press('m')
time.sleep(0.1)
pyautogui.press('enter')
time.sleep(0.5)
pyautogui.write('list.pdf', interval=0.05)
pyautogui.press('enter')
time.sleep(0.1)
pyautogui.press('left')
time.sleep(0.1)
pyautogui.press('enter')
time.sleep(0.5)
pyautogui.press('alt')
time.sleep(0.1)
pyautogui.press('f')
time.sleep(0.1)
pyautogui.press('x')
time.sleep(0.5)
pyautogui.press('alt')
time.sleep(0.1)
pyautogui.press('f')
time.sleep(0.1)
pyautogui.press('x')

