# main.py inside the package "poppy_ai"
from flask import Flask, render_template
from routes.youtube_routes import youtube_bp  # note the dot before youtube_routes

app = Flask(__name__)

app.register_blueprint(youtube_bp)

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/chat')
def chatbot():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == "__main__":
    app.run(debug=True)
