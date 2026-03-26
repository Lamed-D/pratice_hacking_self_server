import requests

def get_compiler_id(target="gcc_x64"):
    try:
        resp = requests.get("https://godbolt.org/api/compilers", headers={"Accept": "application/json"})
        compilers = resp.json()
        if target == "gcc_x64": return "cg132"
        elif target == "gcc_x86": return "cg132"
        elif target == "msvc_x64":
            for c in compilers:
                if "vcpp" in c["id"] and "x64" in c["id"]: return c["id"]
        elif target == "msvc_x86":
            for c in compilers:
                if "vcpp" in c["id"] and "x86" in c["id"] and "x64" not in c["id"]: return c["id"]
    except:
        pass
    if "msvc_x64" == target: return "vcpp_v19_latest_x64"
    if "msvc_x86" == target: return "vcpp_v19_latest_x86"
    return "cg132"

def compile_to_assembly(source_code: str, compiler_choice: str = 'gcc_x64', user_options: str = "") -> str:
    """Godbolt API를 호출하여 C++ 코드를 선택한 설정의 어셈블리로 변환합니다."""
    compiler_id = get_compiler_id(compiler_choice)
    args = "-O0"
    
    if compiler_choice == "gcc_x64": args = "-O0 -m64"
    elif compiler_choice == "gcc_x86": args = "-O0 -m32"
    elif compiler_choice == "msvc_x64": args = "/Od"
    elif compiler_choice == "msvc_x86": args = "/Od"
    
    url = f"https://godbolt.org/api/compiler/{compiler_id}/compile"
    
    payload = {
        "source": source_code,
        "options": {
            "userArguments": args,
            "compilerOptions": {
                "produceAst": False,
                "produceOptInfo": False
            },
            "filters": {
                "labels": True,
                "directives": True,
                "commentOnly": True,
                "intel": True,
                "demangle": True
            }
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers={"Accept": "application/json"})
        response.raise_for_status()
        data = response.json()
        
        if data['code'] != 0: # Compilation error
            error_msg = "\n".join([item.get('text', '') for item in data.get('stderr', [])])
            return f"Error compiling code:\n{error_msg}"
            
        # Extract and filter assembly
        clean_lines = []
        for item in data.get("asm", []):
            text = item.get("text", "")
            t_strip = text.strip()
            if not t_strip: 
                continue
            if t_strip.startswith(';'): 
                continue
            if t_strip.startswith('#'): 
                continue
            if t_strip.startswith('$LN'): 
                continue
            if t_strip.startswith('INCLUDELIB') or t_strip.startswith('include') or t_strip.startswith('PUBLIC'): 
                continue
                
            source = item.get("source")
            if source and source.get("line"):
                text += f" ; ##LINE:{source['line']}"
                
            clean_lines.append(text)
            
        return "\n".join(clean_lines)
        
    except Exception as e:
        return f"Error compiling code: {repr(e)}"
