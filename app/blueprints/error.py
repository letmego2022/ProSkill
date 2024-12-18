from flask import Blueprint, render_template

error_bp = Blueprint('eror', __name__)


# Custom error handler for 404 errors
@error_bp.errorhandler(404)
def page_not_found(error):
    return render_template('error.html', message="Page not found. Please check the URL or return home."), 404

# Custom error handler for 500 errors
@error_bp.errorhandler(500)
def internal_error(error):
    return render_template('error.html', message="An unexpected error occurred. Please try again later."), 500

# Example route to simulate a missing template or unauthorized access
@error_bp.route('/some_page')
def some_page():
    # Simulate a TemplateNotFound error
    return render_template('non_existing_template.html')  # This will trigger the error handler

