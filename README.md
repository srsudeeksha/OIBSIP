# Oasis Infobyte Internship - Python Programming Projects (OIBSIP)

> The repository is named `OIBSIP` because the Oasis Infobyte internship programme asks every intern to use exactly that name.
> It contains three desktop apps built with Python and tkinter: a BMI Calculator, a Random Password Generator and a Weather App.

**Intern:** Sannidhi Ranga Sudeeksha  
**Track:** Python Programming  
**Batch:** November - December 2026

This repository holds my submissions for the Oasis Infobyte internship (AICTE OIB-SIP programme). The Python Programming track asks for at least 3 of 5 tasks; I built three of them at the **Advanced tier**, each as a desktop GUI app with its own README, tests and screenshots.

| Task | Project | What it does | Tests |
|---|---|---|---|
| 2 | [BMI Calculator](Python-Task2-BMICalculator) | tkinter GUI, colour-coded BMI result, multi-user SQLite history, matplotlib trend chart | 47 |
| 3 | [Random Password Generator](Python-Task3-PasswordGenerator) | tkinter GUI, `secrets`-based generation, strength bar, clipboard copy, ambiguous-character option, last-5 history | 42 |
| 4 | [Weather App](Python-Task4-WeatherApp) | tkinter GUI, live current / 6-hour / 5-day forecast with icons, C/F switch, errors shown in the window | 45 |

Tasks 1 (Voice Assistant) and 5 (Chat Application) were not attempted - the track requires a minimum of three tasks.

## Folder layout

```
OIBSIP/
  Python-Task2-BMICalculator/      app.py, bmi_core.py, tests, README, screenshots
  Python-Task3-PasswordGenerator/  app.py, password_core.py, password_cli.py, tests, README, screenshots
  Python-Task4-WeatherApp/         app.py, weather_core.py, tests, README, screenshots
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
