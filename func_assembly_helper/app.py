from flask import Flask, render_template, request, jsonify
from core.godbolt import compile_to_assembly
from core.simulator import simulate_assembly

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/compile_and_simulate', methods=['POST'])
def compile_and_simulate():
    data = request.json
    source_code = data.get('code', '')
    compiler_options = data.get('options', '-O0')
    compiler_choice = data.get('compiler', 'gcc_x64')
    stdin_data = data.get('stdin', '')
    
    arch = "x86" if "x86" in compiler_choice else "x64"
    
    if not source_code:
        return jsonify({"error": "No source code provided"}), 400
        
    # 1. Godbolt API에서 어셈블리 파싱
    assembly_text = compile_to_assembly(source_code, compiler_choice, compiler_options)
    
    if "Error compiling" in assembly_text:
         return jsonify({"error": assembly_text}), 500
         
    # 2. 파이썬 기반 시뮬레이터에서 상태 History 생성 (목업/초기)
    try:
        simulation_states = simulate_assembly(assembly_text, arch, stdin_data)
    except Exception as e:
        return jsonify({"error": f"Simulation Error: {str(e)}"}), 500
    
    return jsonify({
        "assembly": assembly_text,
        "states": simulation_states
    })

@app.route('/api/simulate_only', methods=['POST'])
def simulate_only():
    data = request.json
    code = data.get('assembly', '')
    arch = data.get('arch', 'x64')
    stdin_data = data.get('stdin', '')
    
    try:
        states = simulate_assembly(code, arch=arch, stdin_data=stdin_data)
        return jsonify({
            "assembly": code,
            "states": states
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/simulate_custom', methods=['POST'])
def handle_simulate_custom():
    data = request.json
    code = data.get('code', '')
    compiler_choice = data.get('compiler', 'gcc_x64')
    stdin_data = data.get('stdin', '')
    
    arch = "x86" if "x86" in compiler_choice else "x64"
    try:
        states = simulate_assembly(code, arch=arch, stdin_data=stdin_data)
        return jsonify({
            "assembly": code,
            "states": states
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
