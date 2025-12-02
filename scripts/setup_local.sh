#!/usr/bin/env bash
set -euo pipefail

echo "\n=== WolfKey Local Setup Script ===\n"

# Check for required dependencies
echo "Checking dependencies..."

PYTHON=python3
VENV_DIR=".venv"
MISSING_DEPS=()

# Check Python
if ! command -v $PYTHON >/dev/null 2>&1; then
  echo "❌ Python 3 is not installed or not on PATH."
  MISSING_DEPS+=("python3")
else
  echo "✅ Python: $($PYTHON --version 2>&1)"
fi

# Check PostgreSQL
if ! command -v psql >/dev/null 2>&1; then
  echo "⚠️  PostgreSQL (psql) not found."
  MISSING_DEPS+=("postgresql")
else
  echo "✅ PostgreSQL: $(psql --version 2>&1 | head -1)"
fi

# Check Homebrew (macOS only)
if [[ "$OSTYPE" == "darwin"* ]]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "⚠️  Homebrew not found (recommended for macOS)."
    MISSING_DEPS+=("homebrew")
  else
    echo "✅ Homebrew: $(brew --version 2>&1 | head -1)"
  fi
fi

# If critical dependencies are missing, show install instructions
if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
  echo "\n⚠️  Missing dependencies detected: ${MISSING_DEPS[*]}"
  echo ""
  
  # Offer to install Homebrew first (macOS only)
  if [[ " ${MISSING_DEPS[*]} " =~ " homebrew " ]] && [[ "$OSTYPE" == "darwin"* ]]; then
    echo "📦 Homebrew is a package manager for macOS that makes installing software easy."
    read -p "Would you like to install Homebrew now? [Y/n]: " install_brew
    install_brew=${install_brew:-Y}
    if [[ "$install_brew" =~ ^[Yy] ]]; then
      echo "Installing Homebrew..."
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      
      # Check if brew is now available (might need to update PATH)
      if command -v brew >/dev/null 2>&1; then
        echo "✅ Homebrew installed successfully!"
        # Remove from missing deps
        MISSING_DEPS=("${MISSING_DEPS[@]/homebrew}")
      else
        echo "⚠️  Homebrew installed but not in PATH. You may need to restart your terminal."
        echo "   Or add Homebrew to PATH: eval \"\$(/opt/homebrew/bin/brew shellenv)\""
      fi
    else
      echo "Skipping Homebrew installation."
    fi
    echo ""
  fi
  
  # Offer to install PostgreSQL
  if [[ " ${MISSING_DEPS[*]} " =~ " postgresql " ]]; then
    echo "📦 PostgreSQL is the database system required by WolfKey."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
      if command -v brew >/dev/null 2>&1; then
        read -p "Would you like to install PostgreSQL via Homebrew now? [Y/n]: " install_pg
        install_pg=${install_pg:-Y}
        if [[ "$install_pg" =~ ^[Yy] ]]; then
          echo "Installing PostgreSQL..."
          brew install postgresql@15
          echo "Starting PostgreSQL service..."
          brew services start postgresql@15
          
          # Wait a moment for service to start
          sleep 2
          
          if command -v psql >/dev/null 2>&1; then
            echo "✅ PostgreSQL installed and started successfully!"
            MISSING_DEPS=("${MISSING_DEPS[@]/postgresql}")
          else
            echo "⚠️  PostgreSQL installed but psql not found. You may need to add it to PATH."
          fi
        else
          echo "Skipping PostgreSQL installation."
        fi
      else
        echo "Install PostgreSQL manually with:"
        echo "   brew install postgresql@15"
        echo "   brew services start postgresql@15"
        echo ""
        read -p "Have you installed PostgreSQL? [y/N]: " pg_installed
        if [[ "$pg_installed" =~ ^[Yy] ]]; then
          MISSING_DEPS=("${MISSING_DEPS[@]/postgresql}")
        fi
      fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
      echo "Install PostgreSQL with one of these commands:"
      echo "   sudo apt install postgresql postgresql-contrib  # Ubuntu/Debian"
      echo "   sudo yum install postgresql-server postgresql-contrib  # CentOS/RHEL"
      echo ""
      read -p "Would you like to try automatic installation? (requires sudo) [y/N]: " install_pg_linux
      if [[ "$install_pg_linux" =~ ^[Yy] ]]; then
        if command -v apt-get >/dev/null 2>&1; then
          sudo apt update && sudo apt install -y postgresql postgresql-contrib
          sudo systemctl start postgresql
          sudo systemctl enable postgresql
        elif command -v yum >/dev/null 2>&1; then
          sudo yum install -y postgresql-server postgresql-contrib
          sudo postgresql-setup initdb
          sudo systemctl start postgresql
          sudo systemctl enable postgresql
        fi
        
        if command -v psql >/dev/null 2>&1; then
          echo "✅ PostgreSQL installed successfully!"
          MISSING_DEPS=("${MISSING_DEPS[@]/postgresql}")
        fi
      fi
    fi
    echo ""
  fi
  
  # Final check - if Python is missing, we must exit
  if [[ " ${MISSING_DEPS[*]} " =~ " python3 " ]]; then
    echo "❌ Cannot continue without Python 3."
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
      echo "Install Python 3 with: brew install python3"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
      echo "Install Python 3 with:"
      echo "   sudo apt install python3 python3-pip python3-venv  # Ubuntu/Debian"
      echo "   sudo yum install python3 python3-pip  # CentOS/RHEL"
    fi
    exit 1
  fi
  
  # If PostgreSQL is still missing, ask if they want to continue
  if [[ " ${MISSING_DEPS[*]} " =~ " postgresql " ]]; then
    echo "⚠️  PostgreSQL is still not installed."
    read -p "Continue setup without PostgreSQL? (you'll need to install it later) [y/N]: " continue_without_pg
    if [[ ! "$continue_without_pg" =~ ^[Yy] ]]; then
      echo "Setup cancelled. Install PostgreSQL and run this script again."
      exit 1
    fi
    echo "Continuing without PostgreSQL. You'll need to install it before running the application."
  fi
  
  echo ""
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment at $VENV_DIR..."
  $PYTHON -m venv "$VENV_DIR"
else
  echo "Virtual environment already exists at $VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
PY_BIN="$VENV_DIR/bin/python"

echo "Upgrading pip and installing requirements..."
$PIP install --upgrade pip wheel >/dev/null
$PIP install -r requirements.txt

# Generate random keys
echo "Generating secure random keys..."
SECRET_KEY=$($PY_BIN -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
FERNET_KEY=$($PY_BIN -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Create .env from example if missing
if [ ! -f ".env" ]; then
  echo "\n--- Database Configuration ---"
  read -p "Database name [schoolforumdb]: " db_name
  db_name=${db_name:-schoolforumdb}
  
  read -p "Database user [$(whoami)]: " db_user
  db_user=${db_user:-$(whoami)}
  
  read -sp "Database password (hidden): " db_password
  echo ""
  
  read -p "Database host [localhost]: " db_host
  db_host=${db_host:-localhost}
  
  read -p "Database port [5432]: " db_port
  db_port=${db_port:-5432}
  
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "Created .env from .env.example."
  else
    cat > .env <<EOF
DEBUG=True

# Email (optional)
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=
SITE_URL=http://localhost:8000
EOF
    echo "Created .env file."
  fi
  
  # Add database config and generated keys to .env
  {
    echo ""
    echo "# Database Configuration"
    echo "DB_NAME=$db_name"
    echo "DB_USER=$db_user"
    echo "DB_PASSWORD=$db_password"
    echo "DB_HOST=$db_host"
    echo "DB_PORT=$db_port"
    echo ""
    echo "# Auto-generated keys"
    echo "SECRET_KEY=$SECRET_KEY"
    echo "FERNET_KEY=$FERNET_KEY"
  } >> .env
  
  echo "✅ Created .env with your database credentials and auto-generated keys."
else
  echo ".env already exists — leaving it alone."
fi

# Try to create local Postgres database (best-effort)
if command -v psql >/dev/null 2>&1; then
  echo "\n--- Database Setup ---"
  read -p "Attempt to create database '$db_name'? (Y/n): " create_db
  create_db=${create_db:-Y}
  if [[ "$create_db" =~ ^[Yy] ]]; then
    if createdb "$db_name" 2>/dev/null; then
      echo "✅ Created database '$db_name'."
    else
      echo "⚠️  Could not create database '$db_name' (it may already exist or you may lack permissions)."
    fi
  else
    echo "Skipping database creation. Make sure the database exists before running migrations."
  fi
else
  echo "⚠️  psql not found; skipping automatic DB creation. Install PostgreSQL or create the DB manually."
fi

echo "Running Django migrations..."
$PY_BIN manage.py migrate

echo "\nMigrations complete."

read -p "Create Django superuser now? (Y/n): " create_su
create_su=${create_su:-Y}
if [[ "$create_su" =~ ^[Yy] ]]; then
  $PY_BIN manage.py createsuperuser
else
  echo "Skipping superuser creation. You can run: $PY_BIN manage.py createsuperuser"
fi

echo "\nSetup finished. Activate your venv with:\n  source $VENV_DIR/bin/activate\n"
