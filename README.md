# OIBSIP - Oasis Infobyte Internship Projects

**Intern:** Sannidhi Ranga Sudeeksha  
**Track:** Python Programming  
**Batch:** November - December 2026

This repository holds my submissions for the Oasis Infobyte internship (AICTE OIB-SIP programme). The Python Programming track asks for at least 3 of 5 tasks; I built three of them at the **Advanced tier**, each as a desktop GUI app with its own README, tests and screenshots.

| Task | Project | What it does | Demo video | Tests |
|---|---|---|---|---|
| 2 | [BMI Calculator](Python-Task2-BMICalculator) | tkinter GUI, colour-coded BMI result, multi-user SQLite history, matplotlib trend chart | [Watch](Python-Task2-BMICalculator/demo/Python-Task2-BMICalculator-demo.mp4) | 47 |
| 3 | [Random Password Generator](Python-Task3-PasswordGenerator) | tkinter GUI, `secrets`-based generation, strength bar, clipboard copy, ambiguous-character option, last-5 history | [Watch](Python-Task3-PasswordGenerator/demo/Python-Task3-PasswordGenerator-demo.mp4) | 42 |
| 4 | [Weather App](Python-Task4-WeatherApp) | tkinter GUI, live current / 6-hour / 5-day forecast with icons, C/F switch, errors shown in the window | [Watch](Python-Task4-WeatherApp/demo/Python-Task4-WeatherApp-demo.mp4) | 45 |

## Folder layout

```
OIBSIP/
  Python-Task2-BMICalculator/      app.py, bmi_core.py, tests, README, screenshots, demo video
  Python-Task3-PasswordGenerator/  app.py, password_core.py, password_cli.py, tests, README, screenshots, demo video
  Python-Task4-WeatherApp/         app.py, weather_core.py, tests, README, screenshots, demo video
```

Each project keeps the logic (`*_core.py`) separate from the GUI (`app.py`), so the logic can be unit tested without opening a window. A small `theme.py` (the same file in every project, with a different accent colour per app) gives all three GUIs one consistent modern look using plain tkinter - no extra UI packages.

## Running a project

Needs Python 3.9 or newer with tkinter (included in the standard Windows / macOS installers). Tested on Windows 11 with Python 3.13.

```bash
cd Python-Task2-BMICalculator          # or Python-Task3-PasswordGenerator / Python-Task4-WeatherApp
pip install -r requirements.txt
python app.py
python -m pytest -q                    # run that project's tests
```

The GUI smoke tests open real (hidden) tkinter windows, so they need a desktop session; the other tests run anywhere. The Weather App tests are fully offline.
