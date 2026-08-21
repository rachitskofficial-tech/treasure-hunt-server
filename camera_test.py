from flask import render_template
import app as app_module


@app_module.app.route('/camera-test')
def camera_test():
    return render_template('camera_test.html')
