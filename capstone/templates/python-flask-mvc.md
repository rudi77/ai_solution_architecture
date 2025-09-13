# Python Flask MVC Template

## Description
Flask web service with Model-View-Controller (MVC) architecture pattern

## Architecture Pattern
- **Model-View-Controller (MVC)**
- **Flask BluePrints for modular organization**
- **SQLAlchemy ORM for data access**
- **Flask-RESTful for API endpoints**

## Project Structure
```
app/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── user.py
├── views/
│   ├── __init__.py
│   └── user_views.py
├── controllers/
│   ├── __init__.py
│   └── user_controller.py
├── services/
│   ├── __init__.py
│   └── user_service.py
├── config/
│   ├── __init__.py
│   └── config.py
└── utils/
    ├── __init__.py
    └── validators.py
migrations/
tests/
├── __init__.py
├── test_models.py
├── test_views.py
└── test_services.py
requirements.txt
run.py
config.py
Dockerfile
.env.example
.gitignore
README.md
```

## Code Examples

### run.py
```python
"""Flask application entry point."""

from app import create_app
import os

app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

### app/__init__.py
```python
"""Flask application factory."""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from app.config.config import config

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_name='development'):
    """Create Flask application."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Register blueprints
    from app.views.user_views import user_bp
    app.register_blueprint(user_bp, url_prefix='/api/v1/users')
    
    # Health check endpoint
    @app.route('/health')
    def health():
        return {'status': 'healthy'}, 200
    
    return app
```

### app/config/config.py
```python
"""Flask configuration."""

import os
from datetime import timedelta


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    JSON_SORT_KEYS = False


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///dev.db'


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///prod.db'


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
```

### app/models/user.py
```python
"""User model."""

from datetime import datetime
from app import db


class User(db.Model):
    """User model class."""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def to_dict(self):
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create(cls, email, name):
        """Create a new user."""
        user = cls(email=email, name=name)
        db.session.add(user)
        db.session.commit()
        return user
    
    def update(self, **kwargs):
        """Update user attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
        db.session.commit()
        return self
    
    def delete(self):
        """Delete user."""
        db.session.delete(self)
        db.session.commit()
    
    @classmethod
    def get_by_id(cls, user_id):
        """Get user by ID."""
        return cls.query.get(user_id)
    
    @classmethod
    def get_by_email(cls, email):
        """Get user by email."""
        return cls.query.filter_by(email=email).first()
    
    @classmethod
    def get_all(cls):
        """Get all users."""
        return cls.query.all()
```

### app/services/user_service.py
```python
"""User service layer."""

from app.models.user import User
from app.utils.validators import validate_email, validate_name


class UserService:
    """User service for business logic."""
    
    @staticmethod
    def create_user(email, name):
        """Create a new user with validation."""
        # Validate input
        validate_email(email)
        validate_name(name)
        
        # Check if user already exists
        existing_user = User.get_by_email(email)
        if existing_user:
            raise ValueError(f"User with email {email} already exists")
        
        # Create user
        return User.create(email=email, name=name)
    
    @staticmethod
    def get_user(user_id):
        """Get user by ID."""
        user = User.get_by_id(user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found")
        return user
    
    @staticmethod
    def update_user(user_id, **kwargs):
        """Update user."""
        user = User.get_by_id(user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found")
        
        # Validate updates
        if 'email' in kwargs:
            validate_email(kwargs['email'])
            # Check email uniqueness
            existing = User.get_by_email(kwargs['email'])
            if existing and existing.id != user_id:
                raise ValueError(f"Email {kwargs['email']} already in use")
        
        if 'name' in kwargs:
            validate_name(kwargs['name'])
        
        return user.update(**kwargs)
    
    @staticmethod
    def delete_user(user_id):
        """Delete user."""
        user = User.get_by_id(user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found")
        
        user.delete()
        return True
    
    @staticmethod
    def list_users():
        """List all users."""
        return User.get_all()
```

### app/controllers/user_controller.py
```python
"""User controller."""

from app.services.user_service import UserService


class UserController:
    """User controller for handling business operations."""
    
    def __init__(self):
        self.user_service = UserService()
    
    def create_user(self, data):
        """Handle user creation request."""
        try:
            email = data.get('email')
            name = data.get('name')
            
            if not email or not name:
                return {
                    'success': False,
                    'message': 'Email and name are required',
                    'data': None
                }, 400
            
            user = self.user_service.create_user(email, name)
            return {
                'success': True,
                'message': 'User created successfully',
                'data': user.to_dict()
            }, 201
            
        except ValueError as e:
            return {
                'success': False,
                'message': str(e),
                'data': None
            }, 400
        except Exception as e:
            return {
                'success': False,
                'message': 'Internal server error',
                'data': None
            }, 500
    
    def get_user(self, user_id):
        """Handle get user request."""
        try:
            user = self.user_service.get_user(user_id)
            return {
                'success': True,
                'message': 'User found',
                'data': user.to_dict()
            }, 200
            
        except ValueError as e:
            return {
                'success': False,
                'message': str(e),
                'data': None
            }, 404
        except Exception as e:
            return {
                'success': False,
                'message': 'Internal server error',
                'data': None
            }, 500
    
    def update_user(self, user_id, data):
        """Handle user update request."""
        try:
            user = self.user_service.update_user(user_id, **data)
            return {
                'success': True,
                'message': 'User updated successfully',
                'data': user.to_dict()
            }, 200
            
        except ValueError as e:
            return {
                'success': False,
                'message': str(e),
                'data': None
            }, 400
        except Exception as e:
            return {
                'success': False,
                'message': 'Internal server error',
                'data': None
            }, 500
    
    def delete_user(self, user_id):
        """Handle user deletion request."""
        try:
            self.user_service.delete_user(user_id)
            return {
                'success': True,
                'message': 'User deleted successfully',
                'data': None
            }, 200
            
        except ValueError as e:
            return {
                'success': False,
                'message': str(e),
                'data': None
            }, 404
        except Exception as e:
            return {
                'success': False,
                'message': 'Internal server error',
                'data': None
            }, 500
    
    def list_users(self):
        """Handle list users request."""
        try:
            users = self.user_service.list_users()
            return {
                'success': True,
                'message': 'Users retrieved successfully',
                'data': [user.to_dict() for user in users]
            }, 200
            
        except Exception as e:
            return {
                'success': False,
                'message': 'Internal server error',
                'data': None
            }, 500
```

### app/views/user_views.py
```python
"""User views (API endpoints)."""

from flask import Blueprint, request, jsonify
from app.controllers.user_controller import UserController

user_bp = Blueprint('users', __name__)
user_controller = UserController()


@user_bp.route('/', methods=['POST'])
def create_user():
    """Create a new user."""
    data = request.get_json()
    result, status_code = user_controller.create_user(data)
    return jsonify(result), status_code


@user_bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get user by ID."""
    result, status_code = user_controller.get_user(user_id)
    return jsonify(result), status_code


@user_bp.route('/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update user."""
    data = request.get_json()
    result, status_code = user_controller.update_user(user_id, data)
    return jsonify(result), status_code


@user_bp.route('/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete user."""
    result, status_code = user_controller.delete_user(user_id)
    return jsonify(result), status_code


@user_bp.route('/', methods=['GET'])
def list_users():
    """List all users."""
    result, status_code = user_controller.list_users()
    return jsonify(result), status_code
```

### app/utils/validators.py
```python
"""Validation utilities."""

import re


def validate_email(email):
    """Validate email format."""
    if not email:
        raise ValueError("Email is required")
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise ValueError("Invalid email format")


def validate_name(name):
    """Validate name."""
    if not name:
        raise ValueError("Name is required")
    
    if len(name.strip()) < 2:
        raise ValueError("Name must be at least 2 characters long")
    
    if len(name) > 100:
        raise ValueError("Name cannot exceed 100 characters")
```

### requirements.txt
```
Flask==3.0.0
Flask-SQLAlchemy==3.0.5
Flask-Migrate==4.0.5
Flask-CORS==4.0.0
python-dotenv==1.0.0
```

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "run.py"]
```

### .env.example
```
FLASK_ENV=development
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///app.db
```

### .gitignore
```
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

instance/
.webassets-cache

.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

.pytest_cache/
.coverage
htmlcov/

*.db
migrations/

.vscode/
.idea/
*.swp
*.swo
```

### README.md
```markdown
# Flask MVC Service

A Flask web service implementing Model-View-Controller (MVC) architecture pattern.

## Architecture

This project follows MVC architecture principles:

- **Model**: Data layer with SQLAlchemy ORM
- **View**: API endpoints and request handling
- **Controller**: Business logic coordination
- **Service**: Business logic implementation

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up database:
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

3. Run the application:
```bash
python run.py
```

4. Access the API:
- API: http://localhost:5000
- Health check: http://localhost:5000/health

## API Endpoints

- `POST /api/v1/users/` - Create a new user
- `GET /api/v1/users/{user_id}` - Get user by ID
- `PUT /api/v1/users/{user_id}` - Update user
- `DELETE /api/v1/users/{user_id}` - Delete user
- `GET /api/v1/users/` - List all users
- `GET /health` - Health check

## Testing

Run tests with:
```bash
pytest tests/
```

## Environment Variables

Copy `.env.example` to `.env` and configure:
- `FLASK_ENV` - Flask environment (development/production)
- `SECRET_KEY` - Flask secret key
- `DATABASE_URL` - Database connection string

## Docker

Build and run with Docker:
```bash
docker build -t flask-mvc-service .
docker run -p 5000:5000 flask-mvc-service
```
```

## Template Usage Notes

This template creates a complete Flask service with:

1. **MVC Architecture** - Clear separation of concerns
2. **SQLAlchemy ORM** - Database abstraction layer
3. **Flask Blueprints** - Modular application structure
4. **Database Migrations** - Version control for database schema
5. **Validation Layer** - Input validation utilities
6. **Service Layer** - Business logic separation
7. **RESTful API** - Complete CRUD operations
8. **Error Handling** - Consistent error responses

The template follows Flask best practices for:
- Application factory pattern
- Blueprint organization
- Database management
- Configuration management
- Testing structure