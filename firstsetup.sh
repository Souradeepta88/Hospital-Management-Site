python3 -m venv env
source env/bin/activate  # On Windows use `env\Scripts\activate`
echo "Flask" > requirements.txt
pip install -r requirements.txt
echo "from flask import Flask, render_template
      app = Flask(__name__)\n\n@app.route('/')
      def hello_world():
          return render_template('index.jinja2.html')"> app.py
flask run --reload --port=5001 
mkdir templates
