# WolfKey

WolfKey is a Django-based forum application where users can create posts, add solutions, and comment on solutions. The application supports user registration, login, and logout functionalities. It is designed to be beginner-friendly and easy to set up.

## Table of Contents

- [Description](#description)
- [Installation](#installation)
- [Usage](#usage)
- [Features](#features)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [File Structure Overview](#file-structure-overview)
- [Running Tests](#running-tests)
- [Common Issues](#common-issues)

## Description

WolfKey is a collaborative student forum platform that allows users to ask questions, provide solutions, and interact through comments. It features user authentication, notifications, and a clean web interface.

## Installation

1. **Clone the repository:**
    ```sh
    git clone https://github.com/HugoC1000/WolfKey.git
    cd WolfKey/
    ```

2. **Create and activate a virtual environment:**
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. **Install the dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

4. **Install PostgreSQL:**
    ```sh
    brew install postgresql
    # For Windows users, download from https://www.postgresql.org/download/windows/
    ```

    Start the PostgreSQL service:
    ```sh
    brew services start postgresql
    ```

5. **Set up PostgreSQL:**
    ```sh
    initdb /usr/local/var/postgres
    createuser --interactive
    createdb student_forum
    ```

    Set a password for the PostgreSQL user:
    ```sh
    psql
    \password <your-username>
    \q
    ```

6. **Configure Django to use PostgreSQL:**

    Update your `student_forum/settings.py` file:
    ```python
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'student_forum',
            'USER': '<your-username>',
            'PASSWORD': '<your-password>',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }
    ```

7. **Apply the migrations:**
    ```sh
    python manage.py migrate
    ```

8. **Create a superuser:**
    ```sh
    python manage.py createsuperuser
    ```

9. **Run the development server:**
    ```sh
    python manage.py runserver
    ```

10. **Configure Tasks (Optional)**

    If you want to test email notifications, and functionality involving WolfNet integration, you would have to follow instructions in LOCAL_DEVELOPMENT.md

## Usage

- Access the site at `http://localhost:8000/`
- Register a new account or log in.
- Create, view, and interact with posts and solutions.
- Use the search and notification features to stay updated.

## Features

- User registration, login, and logout
- Post creation, editing, and deletion
- Solution and comment system
- Notifications for activity
- Post following and saving
- Search for posts and users
- Customizable user profiles

## Configuration

- Update `student_forum/settings.py` for database and other settings.
- Static files are managed in the `static/` directory.
- Media uploads (e.g., profile pictures) are stored in the `media/` directory.

## Contributing

### Codebase Structure

WolfKey uses a modular Django architecture:

- **Templates:** HTML files in `forum/templates/` define the UI and are rendered by views.
- **Views:** Python files in `forum/views/` handle HTTP requests, call services, and render templates.
- **Services:** Business logic is separated into `forum/services/` for maintainability. Views call these services to interact with models and perform actions.
- **Models:** Defined in `forum/models.py`, these represent the database structure.
- **Forms:** User input forms are defined in `forum/forms.py`.
- **Static:** CSS, JS, and images are in `static/`.
- **Management Commands:** Custom scripts are in `forum/management/commands/`.
- **Templatetags:** Custom template filters and tags are in `forum/templatetags/`.
- **API:** API endpoints are in `forum/api/`.
- **Tests:** Automated tests are in `forum/tests/`.

**Typical flow:**  
Templates → Views → Services → Models → Database

### File Structure Overview

- `manage.py`: Django’s command-line utility.
- `student_forum/`: Project settings and URLs.
  - `settings.py`: Main configuration.
  - `urls.py`: URL routing.
- `forum/`: Main app.
  - `models.py`: Database models (User, Post, Solution, etc.).
  - `views/`: Handles web requests and responses.
  - `services/`: Contains business logic for posts, comments, profiles, etc.
  - `forms.py`: Django forms for user input.
  - `templates/`: HTML templates for all pages and components.
  - `static/`: CSS, JS, images.
  - `management/commands/`: Custom Django management commands.
  - `templatetags/`: Custom template filters and tags.
  - `api/`: API endpoints.
  - `tests/`: Automated tests for the forum app.
- `media/`: Uploaded files (profile pictures, etc.).
- `requirements.txt`: Python dependencies.
- `README.md`: This documentation.

### How to Contribute

1. Fork the repository and create a new branch.
2. Make your changes, following the code structure above.
3. Write clear commit messages.
4. Submit a pull request with a description of your changes.

**Tips for Beginners:**
- Start by reading the views and templates to understand the user flow.
- Use the services layer to add or modify business logic.
- For new features, add tests in the `forum/tests/` directory.

## Running Tests

To run the tests, use:
```sh
python manage.py test
```

## Common Issues

- Sometimes `python3` is required instead of `python` (e.g., `python3 -m venv venv`).
- If libraries don't install correctly from `requirements.txt`, try installing them individually with `pip install <package>`.
