# 🐺 WolfKey

<div align="center">

**A collaborative student forum platform built with Django**

[![Django](https://img.shields.io/badge/Django-4.2.16-green.svg)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.10-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Latest-blue.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 📖 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Detailed Installation Guide](#-detailed-installation-guide)
  - [Step 1: Clone the Repository](#step-1-clone-the-repository)
  - [Step 2: Set Up Python Environment](#step-2-set-up-python-environment)
  - [Step 3: Install PostgreSQL](#step-3-install-postgresql)
  - [Step 4: Configure Database](#step-4-configure-database)
  - [Step 5: Set Up Django](#step-5-set-up-django)
  - [Step 6: Run the Application](#step-6-run-the-application)
- [Advanced Setup](#-advanced-setup)
- [Usage Guide](#-usage-guide)
- [Project Architecture](#-project-architecture)
- [Contributing](#-contributing)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)
- [Deployment](#-deployment)
- [License](#-license)

---

## ✨ Features

### Core Functionality
- 🔐 **User Authentication**: Secure registration, login, and logout
- 📝 **Post Management**: Create, edit, delete, and search posts
- ✅ **Solution System**: Mark posts as solved with accepted solutions
- 💬 **Nested Comments**: Threaded discussions on solutions
- 🔔 **Real-time Notifications**: Stay informed about activity on your content
- 🔍 **Advanced Search**: Find posts and users with full-text search
- ⭐ **Post Interactions**: Save, follow, and like posts
- 👤 **User Profiles**: Customizable profiles with profile pictures

### Advanced Features
- 📊 **Grade Tracking**: Integration with WolfNet for grade monitoring
- 📧 **Email Notifications**: Asynchronous email delivery via Celery
- 🗓️ **Schedule Management**: Daily schedule and timetable features
- 🎨 **Responsive Design**: Mobile-friendly interface
- 🔒 **Anonymous Posting**: Option to post anonymously

---

## 🚀 Quick Start

For experienced developers, here's a quick setup:

```bash
# Clone and navigate
git clone https://github.com/HugoC1000/WolfKey.git
cd WolfKey

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL database
createdb student_forum

# Configure environment (create .env file)
# Add your database credentials

Alternatively, run the provided setup script which automates common local setup steps (creates a virtualenv, installs requirements, creates a `.env` from `.env.example`, runs migrations, and prompts to create a superuser):

```bash
# Make the script executable (only needed once)
chmod +x scripts/setup_local.sh

# Run the script
./scripts/setup_local.sh
```

# Run migrations and create superuser
python manage.py migrate
python manage.py createsuperuser

# Start server
python manage.py runserver
```

Visit `http://localhost:8000` 🎉

---

## 📚 Detailed Installation Guide

### Step 1: Clone the Repository

First, get the code on your local machine:

```bash
# Clone the repository
git clone https://github.com/HugoC1000/WolfKey.git

# Navigate into the project directory
cd WolfKey
```

**✅ Checkpoint**: You should now be in the `WolfKey` directory. Verify with `ls` or `dir`.

---

### Step 2: Set Up Python Environment

A virtual environment keeps your project dependencies isolated.

#### Create Virtual Environment

```bash
# Create a virtual environment named 'venv'
python -m venv venv

# If that doesn't work, try with python3:
python3 -m venv venv
```

#### Activate Virtual Environment

**macOS / Linux:**
```bash
source venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

> 💡 **Tip**: You'll see `(venv)` appear at the start of your terminal prompt when activated.

#### Install Python Dependencies

```bash
# Upgrade pip to latest version
pip install --upgrade pip

# Install all required packages
pip install -r requirements.txt
```

---

### Step 3: Install PostgreSQL

WolfKey uses PostgreSQL as its database. Choose your operating system:

If you get brew not found errors, you need to install brew first using 

#### macOS

```bash
# Install PostgreSQL using Homebrew
brew install postgresql@15

# Start PostgreSQL service
brew services start postgresql@15

# Verify installation
psql --version
```
#### Ubuntu/Debian Linux

```bash
# Update package list
sudo apt update

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Verify installation
psql --version
```

#### Windows

1. Download PostgreSQL installer from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/)
2. Run the installer
3. Remember the password you set for the `postgres` user
4. Add PostgreSQL to your PATH (usually done automatically)
5. Verify in Command Prompt: `psql --version`

**✅ Checkpoint**: PostgreSQL should be running. Check with:
- macOS/Linux: `brew services list` or `sudo systemctl status postgresql`
- Windows: Check Services app for "postgresql" service

---

### Step 4: Configure Database

#### Create the Database

**macOS / Linux:**

```bash
# Create database
createdb student_forum

# If you get permission errors, you may need to create a user first:
createuser -s $(whoami)  # Creates a superuser with your username
createdb student_forum
```

**Windows:**

```cmd
# Open psql as postgres user
psql -U postgres

# In psql prompt:
CREATE DATABASE student_forum;
\q
```

#### Set Database Password (Optional but Recommended)

```bash
# Open PostgreSQL prompt
psql student_forum

# In psql, set a password for your user:
\password

# Enter your new password when prompted
# Exit psql:
\q
```

#### Configure Django Database Settings

Create a `.env` file in the project root for sensitive credentials:

```bash
# In the WolfKey directory
touch .env
```

Add the following to `.env`:

```env
# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here-generate-a-random-one

# Database Configuration
DB_NAME=schoolforumdb
DB_USER=your_postgres_username
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432

# Email Settings (optional for local development)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your-email@example.com
SITE_URL=http://localhost:8000
```

> 💡 **Finding your PostgreSQL username**: On macOS, it's typically your system username. Run `whoami` to find it, or use `postgres` if you set up PostgreSQL with the default superuser.

> 🔒 **Security Note**: Never commit `.env` to version control. It's already in `.gitignore`.

---

### Step 5: Set Up Django

#### Run Database Migrations

Migrations create the necessary database tables:

```bash
# Apply all migrations
python manage.py migrate
```

You should see output like:
```
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  ...
```

#### Create a Superuser Account

This account lets you access the admin panel:

```bash
python manage.py createsuperuser
```

You'll be prompted for:
- **Username**: Your admin username
- **Email**: Your email address
- **Password**: Choose a strong password (won't be displayed as you type)

**✅ Checkpoint**: Superuser created successfully.

#### Collect Static Files (Optional for Development)

```bash
python manage.py collectstatic --noinput
```

---

### Step 6: Run the Application

#### Start the Development Server

```bash
python manage.py runserver
```

You should see:
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

#### Access the Application

Open your web browser and navigate to:

- **Main Site**: [http://localhost:8000](http://localhost:8000)
- **Admin Panel**: [http://localhost:8000/admin](http://localhost:8000/admin)

**🎉 Congratulations! WolfKey is now running locally!**

---

## 🔧 Advanced Setup (OPTIONAL)

### Setting Up Background Task Processing

WolfKey uses Celery for background tasks like email notifications and grade checking.

#### 1. Install Redis

**macOS:**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Linux:**
```bash
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

**Windows:**
Download from [github.com/microsoftarchive/redis/releases](https://github.com/microsoftarchive/redis/releases)

#### 2. Verify Redis is Running

```bash
redis-cli ping
# Should return: PONG
```

#### 3. Run Celery Workers

Open **separate terminal windows** for each:

**Terminal 1 - Grades Worker** (handles WebDriver tasks):
```bash
source venv/bin/activate  # Activate virtual environment
celery -A student_forum worker --loglevel=info --concurrency=1 -Q grades --pool=solo
```

**Terminal 2 - General Worker** (handles emails, notifications):
```bash
source venv/bin/activate
celery -A student_forum worker --loglevel=info --concurrency=1 -Q general,high,default,low --pool=solo
```

**Terminal 3 - Celery Beat** (task scheduler):
```bash
source venv/bin/activate
celery -A student_forum beat --loglevel=info
```

**Terminal 4 - Django Server**:
```bash
source venv/bin/activate
python manage.py runserver
```

> 📖 For more details, see [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md)

---

## 📖 Usage Guide

### Creating Your First Post

1. **Register an Account**
   - Go to [http://localhost:8000](http://localhost:8000)
   - Click "Register" and fill out the form

2. **Create a Post**
   - Click "New Post" or "Ask Question"
   - Enter a title and description
   - Add relevant tags
   - Submit

3. **Add a Solution**
   - Navigate to any post
   - Click "Add Solution"
   - Provide a detailed answer
   - Submit

4. **Interact with Content**
   - Upvote/downvote solutions
   - Comment on solutions
   - Follow posts to get notifications
   - Mark a solution as accepted (if it's your post)

### Using the Admin Panel

Access at [http://localhost:8000/admin](http://localhost:8000/admin)

- Manage users, posts, solutions, and comments
- View site statistics
- Moderate content
- Configure site settings

---

## 🏗️ Project Architecture

WolfKey follows a clean, modular Django architecture for maintainability and scalability.

### Directory Structure

```
WolfKey/
├── forum/                      # Main application
│   ├── models.py              # Database models (User, Post, Solution, Comment)
│   ├── views/                 # Request handlers
│   │   ├── __init__.py
│   │   ├── post_views.py     # Post-related views
│   │   ├── user_views.py     # User authentication & profiles
│   │   └── ...
│   ├── services/              # Business logic layer
│   │   ├── post_service.py   # Post operations
│   │   ├── comment_service.py # Comment operations
│   │   └── ...
│   ├── api/                   # REST API endpoints
│   │   ├── posts.py
│   │   ├── comments.py
│   │   └── ...
│   ├── templates/             # HTML templates
│   │   └── forum/
│   ├── static/                # CSS, JavaScript, images
│   ├── forms.py               # Django forms
│   ├── serializers.py         # DRF serializers
│   ├── tasks.py               # Celery async tasks
│   ├── management/            # Custom management commands
│   │   └── commands/
│   ├── templatetags/          # Custom template filters
│   ├── tests/                 # Unit and integration tests
│   └── migrations/            # Database migrations
├── student_forum/             # Project configuration
│   ├── settings.py            # Django settings
│   ├── urls.py                # URL routing
│   ├── celery.py              # Celery configuration
│   └── wsgi.py                # WSGI application
├── media/                     # User uploads
│   ├── profile_pictures/
│   └── uploads/
├── static/                    # Collected static files
├── manage.py                  # Django CLI
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

### Architecture Flow

```
┌─────────┐      ┌────────┐      ┌──────────┐      ┌────────┐      ┌──────────┐
│ Browser │ ───► │ Views  │ ───► │ Services │ ───► │ Models │ ───► │ Database │
└─────────┘      └────────┘      └──────────┘      └────────┘      └──────────┘
     ▲               │                                                      │
     │               ▼                                                      │
     │          ┌──────────┐                                               │
     └───────── │ Templates│                                               │
                └──────────┘                                               │
                                                                            │
┌──────────────┐                                                           │
│ Celery Tasks │ ──────────────────────────────────────────────────────────┘
└──────────────┘   (Background jobs: emails, grade checking)
```

### Key Components

#### **1. Models** (`forum/models.py`)
Defines the database schema:
- `User` - Extended Django user with custom fields
- `Post` - Forum posts with metadata
- `Solution` - Answers to posts
- `Comment` - Threaded comments on solutions
- `Notification` - User notifications
- `UserProfile` - Extended user information
- `DailySchedule` - Schedule management

#### **2. Views** (`forum/views/`)
Handles HTTP requests and responses:
- Receives requests from URLs
- Calls service layer for business logic
- Renders templates with context data
- Returns HTTP responses

#### **3. Services** (`forum/services/`)
Contains business logic (separated from views):
- Post creation, editing, deletion
- User authentication and profile management
- Notification generation
- Search functionality
- Comment and solution handling

**Why Services?** Separating business logic makes code:
- ✅ More testable
- ✅ Reusable across views and APIs
- ✅ Easier to maintain

#### **4. Templates** (`forum/templates/`)
HTML files rendered by views:
- Jinja2-style templating
- Reusable components and layouts
- Dynamic content rendering

#### **5. API** (`forum/api/`)
RESTful API endpoints using Django REST Framework:
- JSON responses
- Token authentication
- Mobile app support
- Third-party integrations

#### **6. Tasks** (`forum/tasks.py`)
Asynchronous background tasks using Celery:
- Email notifications
- Grade checking (with Selenium)
- Scheduled periodic tasks
- Heavy computations

---

## 🤝 Contributing

We welcome contributions! Here's how to get started.

### Getting Started

1. **Fork the Repository**
   - Click "Fork" on GitHub
   - Clone your fork: `git clone https://github.com/YOUR-USERNAME/WolfKey.git`

2. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make Your Changes**
   - Follow the code structure (see [Architecture](#-project-architecture))
   - Write clear, commented code
   - Add tests for new features

4. **Test Your Changes**
   ```bash
   python manage.py test
   ```

5. **Commit and Push**
   ```bash
   git add .
   git commit -m "Add: Brief description of your changes"
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request**
   - Go to your fork on GitHub
   - Click "New Pull Request"
   - Describe your changes

### Code Style Guidelines

- **Python**: Follow PEP 8
- **Naming**: Use descriptive variable and function names
- **Comments**: Explain *why*, not *what*
- **Docstrings**: Use for all functions and classes
- **Imports**: Organize as: standard library, third-party, local

### Where to Start

**For Beginners:**
- Fix typos or improve documentation
- Add tests for existing features
- Improve error messages
- Enhance UI/UX

**For Intermediate:**
- Add new features (check Issues tab)
- Refactor code for better performance
- Implement API endpoints
- Add validation and error handling

**For Advanced:**
- Optimize database queries
- Implement caching strategies
- Add real-time features (WebSockets)
- Improve security

### Development Workflow

---

## 🧪 Testing

WolfKey includes a comprehensive test suite.

### Running Tests

```bash
# Run all tests
python manage.py test

# Run tests for a specific app
python manage.py test forum

# Run a specific test file
python manage.py test forum.tests.test_models

# Run with verbosity for detailed output
python manage.py test --verbosity=2

# Run tests with coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report in htmlcov/
```

### Test Structure

```
forum/tests/
├── __init__.py
├── test_models.py          # Model tests
├── test_views.py           # View tests
├── test_services.py        # Service layer tests
├── test_forms.py           # Form validation tests
└── test_api.py             # API endpoint tests
```

---

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 1. `ModuleNotFoundError: No module named 'psycopg2'`

**Solution:**
```bash
# Make sure virtual environment is activated
pip install psycopg2-binary
```

#### 2. `django.db.utils.OperationalError: could not connect to server`

**Cause:** PostgreSQL is not running.

**Solution:**
```bash
# macOS
brew services start postgresql@15

# Linux
sudo systemctl start postgresql

# Windows
# Start from Services app or pg_ctl start
```

#### 3. `FATAL: database "student_forum" does not exist`

**Solution:**
```bash
createdb student_forum
```

#### 4. `python: command not found`

**Solution:** Use `python3` instead:
```bash
python3 -m venv venv
python3 manage.py runserver
```

#### 5. Virtual environment not activating on Windows PowerShell

**Cause:** Execution policy restriction.

**Solution:**
```powershell
# Run as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then activate
venv\Scripts\Activate.ps1
```

#### 6. `Port 8000 is already in use`

**Solution:**
```bash
# Find and kill the process
# macOS/Linux
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Or run on a different port
python manage.py runserver 8001
```

#### 7. Static files not loading

**Solution:**
```bash
python manage.py collectstatic --noinput
```

#### 8. Redis connection error

**Solution:**
```bash
# Check if Redis is running
redis-cli ping

# If not running:
# macOS
brew services start redis

# Linux
sudo systemctl start redis
```

#### 9. Migration conflicts

**Solution:**
```bash
# Reset migrations (⚠️ USE WITH CAUTION - destroys data)
python manage.py migrate --fake forum zero
python manage.py migrate forum
```

#### 10. Permission denied errors

**Solution:**
```bash
# Ensure proper ownership (macOS/Linux)
sudo chown -R $USER:$USER .

# Or run with proper permissions
chmod +x manage.py
```

## 🚀 Deployment

### Deploying to Heroku

WolfKey is Heroku-ready with included configuration files.

#### Prerequisites
- Heroku account ([signup.heroku.com](https://signup.heroku.com))
- Heroku CLI ([devcenter.heroku.com/articles/heroku-cli](https://devcenter.heroku.com/articles/heroku-cli))

[⬆ Back to Top](#-wolfkey)
</div>
