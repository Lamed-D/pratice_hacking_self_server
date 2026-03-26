import re

def parse_operand(op):
    op = op.strip()
    if op.startswith("DWORD PTR "):
        op = op.replace("DWORD PTR ", "")
    if op.startswith("QWORD PTR "):
        op = op.replace("QWORD PTR ", "")
    if op.startswith("BYTE PTR "):
        op = op.replace("BYTE PTR ", "")
    op = op.replace("OFFSET FLAT:", "").replace("OFFSET ", "")
    return op

def simulate_assembly(assembly_text: str, arch: str = "x64", stdin_data: str = "") -> list:
    states = []
    ptr_size = 4 if arch == "x86" else 8
    
    SP = "ESP" if arch == "x86" else "RSP"
    BP = "EBP" if arch == "x86" else "RBP"
    IP = "EIP" if arch == "x86" else "RIP"
    
    if arch == "x86":
        registers = {
            "EAX": 0, "EBX": 0, "ECX": 0, "EDX": 0,
            "EDI": 0, "ESI": 0,
            SP: 0xffffd000,
            "EBP": 0xffffd020,
            "EIP": "main",
            "XMM0": 0.0, "XMM1": 0.0, "XMM2": 0.0, "XMM3": 0.0,
            "XMM4": 0.0, "XMM5": 0.0, "XMM6": 0.0, "XMM7": 0.0
        }
    else:
        registers = {
            "RAX": 0, "RBX": 0, "RCX": 0, "RDX": 0,
            "RDI": 0, "RSI": 0, "R8": 0, "R9": 0, "R10": 0, "R11": 0,
            "RSP": 0x7fffffffe000,
            "RBP": 0x7fffffffe020,
            "RIP": "main"
        }
        for i in range(16): registers[f"XMM{i}"] = 0.0
    
    flags = {"ZF": 0, "SF": 0, "CF": 0, "OF": 0}
    stack_memory = {}
    data_memory = {}
    console_output = ""
    
    def set_flags(res, op1=None, op2=None, is_sub=False):
        flags["ZF"] = 1 if res == 0 else 0
        flags["SF"] = 1 if res < 0 else 0
        # Basic mock for CF and OF to make branching somewhat realistic
        if op1 is not None and op2 is not None:
            if is_sub:
                flags["CF"] = 1 if op1 < op2 else 0
                flags["OF"] = 1 if (op1 > 0 and op2 < 0 and res < 0) or (op1 < 0 and op2 > 0 and res > 0) else 0
            else:
                flags["CF"] = 1 if res > 0xffffffffffffffff else 0
                flags["OF"] = 1 if (op1 > 0 and op2 > 0 and res < 0) or (op1 < 0 and op2 < 0 and res > 0) else 0
        
    def get_reg_name(name):
        name = name.lower()
        if arch == "x86":
            mapping = {
                "eax":"EAX", "rax":"EAX", "al":"EAX", "ax":"EAX",
                "ebx":"EBX", "rbx":"EBX", "bl":"EBX", "bx":"EBX",
                "ecx":"ECX", "rcx":"ECX", "cl":"ECX", "cx":"ECX",
                "edx":"EDX", "rdx":"EDX", "dl":"EDX", "dx":"EDX",
                "edi":"EDI", "rdi":"EDI", "di":"EDI",
                "esi":"ESI", "rsi":"ESI", "si":"ESI",
                "ebp":"EBP", "rbp":"EBP", "bp":"EBP",
                "esp":"ESP", "rsp":"ESP", "sp":"ESP"
            }
        else:
            mapping = {
                "eax":"RAX", "rax":"RAX", "al":"RAX", "ax":"RAX",
                "ebx":"RBX", "rbx":"RBX", "bl":"RBX", "bx":"RBX",
                "ecx":"RCX", "rcx":"RCX", "cl":"RCX", "cx":"RCX",
                "edx":"RDX", "rdx":"RDX", "dl":"RDX", "dx":"RDX",
                "edi":"RDI", "rdi":"RDI", "di":"RDI",
                "esi":"RSI", "rsi":"RSI", "si":"RSI",
                "r8":"R8", "r8d":"R8", "r9":"R9", "r9d":"R9",
                "r10":"R10", "r10d":"R10", "r11":"R11", "r11d":"R11",
                "ebp":"RBP", "rbp":"RBP", "bp":"RBP",
                "esp":"RSP", "rsp":"RSP", "sp":"RSP"
            }
        
        # Identity fallback for XMM
        if name.upper().startswith("XMM"): return name.upper()
        return mapping.get(name, name.upper())

    def get_addr(expr):
        prefix = ""
        if '[' in expr:
            prefix = expr[:expr.find('[')].strip()
            inner = expr[expr.find('[')+1 : expr.rfind(']')]
        else:
            inner = expr
            
        if '-' in inner:
            base, offset = inner.split('-')
            base_addr = registers.get(get_reg_name(base), 0) - int(offset)
        elif '+' in inner:
            base, offset = inner.split('+')
            base_addr = registers.get(get_reg_name(base), 0) + int(offset)
        else:
            base_addr = registers.get(get_reg_name(inner), 0)
            
        if prefix in equates:
            base_addr += equates[prefix]
            
        return base_addr

    def get_val(op):
        if isinstance(op, int): return op
        if '[' in op and op.endswith(']'):
            addr = get_addr(op)
            val = stack_memory.get(addr, {"val":0})["val"]
            if isinstance(val, int): return val
            if str(val).lstrip('-').isdigit(): return int(val)
            return 0

        if op.isdigit() or (op.startswith("-") and op[1:].isdigit()):
            return int(op)
        reg = get_reg_name(op)
        if reg in registers:
            return registers[reg]
        if op in equates:
            return equates[op]
        # Try finding label in data memory (address mock)
        if op in data_memory:
            return data_memory[op]["addr"]
        return 0

    def format_val(v):
        try:
            val_int = int(v)
            if abs(val_int) > 4096:
                return hex(val_int)
            return str(val_int)
        except:
            return str(v)

    def format_stack():
        sorted_addrs = sorted((k for k in stack_memory.keys() if isinstance(k, int)), reverse=True)
        return [{"address": hex(a), "value": format_val(stack_memory[a]["val"]), "comment": stack_memory[a]["comment"]} for a in sorted_addrs]
        
    def add_state(line_idx, instr, explanation="", cpp_line=None):
        res_regs = {}
        for k, v in registers.items():
            if k in ["RSP", "RBP", "ESP", "EBP"]: res_regs[k] = hex(v)
            elif k.startswith("XMM"): res_regs[k] = f"{v:.4f}" if isinstance(v, float) else str(v)
            else: res_regs[k] = str(v)
            
        states.append({
            "line": line_idx,
            "instruction": instr,
            "explanation": explanation,
            "cpp_line": cpp_line,
            "call_stack": [format_rip(c) for c in call_stack],
            "registers": res_regs,
            "flags": flags.copy(),
            "stack": format_stack(),
            "console_output": console_output,
            "data": data_memory.copy()
        })
        
    lines = assembly_text.split('\n')
    
    labels = {}
    equates = {}
    
    # Pre-parse data segment 
    data_addr_counter = 0x400000
    current_label = None
    
    for i, line in enumerate(lines):
        orig_line = line
        line = line.split(';')[0].split('#')[0].split('//')[0].strip()
        if line.endswith(':'):
            lbl = line[:-1]
            labels[lbl] = i
            current_label = lbl
        elif line.endswith(' PROC'):
            lbl = line[:-5].strip()
            labels[lbl] = i
            if lbl == '_main': labels['main'] = i
            current_label = None
        elif '=' in line and 'DWORD' not in line:
            parts = line.split('=')
            if len(parts) == 2:
                try: equates[parts[0].strip()] = int(parts[1].strip())
                except: pass
        elif line.startswith('.string ') or line.startswith('.asciz ') or line.startswith('.ascii '):
            if current_label:
                str_val = line[line.find('"')+1:line.rfind('"')]
                str_val = str_val.replace('\\n', '\n').replace('\\t', '\t')
                data_memory[current_label] = {"addr": data_addr_counter, "value": str_val, "type": "string"}
                data_addr_counter += len(str_val) + 1
        elif ' DB ' in line and ("'" in line or '"' in line):
            parts = line.split(' DB ', 1)
            lbl = parts[0].strip()
            str_val = parts[1]
            if str_val.startswith("'"): str_val = str_val[1:str_val.find("'", 1)]
            elif str_val.startswith('"'): str_val = str_val[1:str_val.find('"', 1)]
            str_val = str_val.replace('\\n', '\n').replace('\\t', '\t')
            if '0ah' in line.lower() or '0dh' in line.lower():
                str_val += '\n'
            data_memory[lbl] = {"addr": data_addr_counter, "value": str_val, "type": "string"}
            data_addr_counter += len(str_val) + 1
        elif line.startswith('.long ') or line.startswith('.int '):
            if current_label:
                try:
                    val = int(line.split()[1])
                    data_memory[current_label] = {"addr": data_addr_counter, "value": val, "type": "int"}
                    data_addr_counter += 4
                except: pass
            
    sorted_labels = sorted([(v, k) for k, v in labels.items()])

    def format_rip(current_pc):
        last_label = None
        last_pc = 0
        for l_pc, lbl in sorted_labels:
            if l_pc <= current_pc:
                last_label = lbl
                last_pc = l_pc
            else:
                break
        if last_label:
            offset = current_pc - last_pc
            return f"{last_label}+{offset}" if offset > 0 else last_label
        return f"line {current_pc}"

    pc = labels.get('main', labels.get('_main', 0))
    registers[IP] = format_rip(pc)
    
    call_stack = []
    add_state(pc, "Initial State", "Program entry point")
    
    step_limit = 500
    steps = 0
    current_cpp_line = None
    
    # Second pass: execute
    while pc < len(lines) and steps < step_limit:
        steps += 1
        original_pc = pc
        line = lines[pc].strip()
        pc += 1
        
        if "; ##LINE:" in line:
            parts = line.rsplit('; ##LINE:', 1)
            line = parts[0].strip()
            try: current_cpp_line = int(parts[1].strip())
            except ValueError: pass
            
        if not line or line.startswith('.'):
            if steps == 1: # initial state
                add_state(original_pc, line, "Program Start", current_cpp_line)
            continue
        if line.endswith(':') or line.endswith(' PROC') or line.endswith(' ENDP') or '=' in line:
            continue
            
        parts = line.split(None, 1)
        opcode = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        ops = [parse_operand(o) for o in args.split(',')] if args else []
        
        explanation = ""
        try:
            if opcode in ["mov", "movss", "movaps", "movsd"]:
                dest, src = ops[0], ops[1]
                val = get_val(src)
                if '[' in dest and dest.endswith(']'):
                    addr = get_addr(dest)
                    stack_memory[addr] = {"val": str(val), "comment": "local"}
                    explanation = f"Memory write to {dest}"
                else:
                    registers[get_reg_name(dest)] = val
                    explanation = f"Moved {val} into {get_reg_name(dest)}"
                    
            elif opcode == "lea":
                dest, src = ops[0], ops[1]
                if '[' in src and src.endswith(']'):
                    addr = get_addr(src)
                    registers[get_reg_name(dest)] = addr
                    explanation = f"Loaded address {hex(addr)} into {get_reg_name(dest)}"
                else:
                    # Fallback if label
                    val = get_val(src)
                    registers[get_reg_name(dest)] = val
                    explanation = f"Loaded address of {src} into {get_reg_name(dest)}"
                    
            elif opcode == "push":
                val = get_val(ops[0])
                registers[SP] -= ptr_size
                stack_memory[registers[SP]] = {"val": str(val), "comment": f"push {ops[0]}"}
                explanation = f"Pushed {val} onto stack"
                
            elif opcode == "pop":
                dest = get_reg_name(ops[0])
                val = stack_memory.get(registers[SP], {"val":0})["val"]
                registers[dest] = int(val) if str(val).lstrip('-').isdigit() else val
                if registers[SP] in stack_memory:
                    del stack_memory[registers[SP]]
                registers[SP] += ptr_size
                explanation = f"Popped {val} into {dest}"
                
            elif opcode in ["add", "sub", "imul", "xor", "and", "or"]:
                dest = get_reg_name(ops[0])
                val = get_val(ops[1])
                explanation = f"Operation: {dest} {opcode} {val}"
                if dest in registers:
                    op1 = registers[dest]
                    if opcode == "add": registers[dest] += val
                    elif opcode == "sub": registers[dest] -= val
                    elif opcode == "imul": registers[dest] *= val
                    elif opcode == "xor": registers[dest] ^= val
                    elif opcode == "and": registers[dest] &= val
                    elif opcode == "or": registers[dest] |= val
                    set_flags(registers[dest], op1, val, is_sub=(opcode=="sub"))
                    
            elif opcode in ["addss", "subss", "mulss", "divss", "addsd", "subsd", "mulsd", "divsd"]:
                dest = get_reg_name(ops[0])
                val = float(get_val(ops[1]))
                explanation = f"Float Operation: {dest} {opcode} {val}"
                if dest in registers:
                    rval = float(registers[dest])
                    if "add" in opcode: registers[dest] = rval + val
                    elif "sub" in opcode: registers[dest] = rval - val
                    elif "mul" in opcode: registers[dest] = rval * val
                    elif "div" in opcode: registers[dest] = rval / val if val != 0 else float('inf')
                    
            elif opcode == "cvtsi2ss" or opcode == "cvtsi2sd":
                dest, src = get_reg_name(ops[0]), get_val(ops[1])
                registers[dest] = float(src)
                explanation = f"Converted int {src} to float in {dest}"
                
            elif opcode == "cvttss2si" or opcode == "cvttsd2si":
                dest, src = get_reg_name(ops[0]), get_val(ops[1])
                registers[dest] = int(float(src))
                explanation = f"Converted float {src} to int in {dest}"
                
            elif opcode == "inc":
                dest = get_reg_name(ops[0])
                if dest in registers:
                    registers[dest] += 1
                    set_flags(registers[dest], registers[dest]-1, 1, is_sub=False)
                    explanation = f"Incremented {dest}"

            elif opcode == "dec":
                dest = get_reg_name(ops[0])
                if dest in registers:
                    registers[dest] -= 1
                    set_flags(registers[dest], registers[dest]+1, 1, is_sub=True)
                    explanation = f"Decremented {dest}"
                    
            elif opcode == "cmp":
                dest = get_val(ops[0])
                src = get_val(ops[1])
                set_flags(dest - src, dest, src, is_sub=True)
                explanation = f"Compared {dest} with {src}"
                
            elif opcode == "test":
                dest = get_val(ops[0])
                src = get_val(ops[1])
                set_flags(dest & src)
                explanation = f"Logical AND test {ops[0]} & {ops[1]}"

            elif opcode == "call":
                target = args.strip()
                cleanup_target = target.replace('QWORD PTR', '').strip().split('(')[0]
                cleanup_target = cleanup_target.split()[-1] if ' ' in cleanup_target else cleanup_target
                explanation = f"Called function: {target}"
                
                is_intercepted = False
                # Intercept I/O functions
                if "printf" in cleanup_target or "puts" in cleanup_target or "std::" in cleanup_target:
                    is_intercepted = True
                    # In x64 MSVC it's RCX, GCC it's RDI. In x86 it's on the stack but we'll loosely check registers.
                    arg1_vals = [registers.get("RCX", 0), registers.get("RDI", 0), registers.get("ECX", 0), registers.get("EDI", 0)]
                    
                    # Read top of stack for x86 calling convention
                    top_stack_str = stack_memory.get(registers[SP], {}).get("val", "0")
                    try:
                        if isinstance(top_stack_str, str) and top_stack_str.startswith("0x"): arg1_vals.append(int(top_stack_str, 16))
                        else: arg1_vals.append(int(top_stack_str))
                    except ValueError: pass
                    
                    str_to_print = "???"
                    for r_val in arg1_vals:
                        if r_val == 0: continue
                        for k, v in data_memory.items():
                            if v["addr"] == r_val:
                                str_to_print = v["value"]
                                break
                        if str_to_print != "???": break
                        
                    if "printf" not in cleanup_target and "std::" not in cleanup_target: # puts appends newline
                        str_to_print += "\n"
                        
                    if "%d" in str_to_print or "%i" in str_to_print:
                        # Try grabbing x86 arg2 from stack 
                        arg2_str = stack_memory.get(registers[SP] + ptr_size, {}).get("val", "0")
                        arg2_val = 0
                        try:
                            arg2_val = int(arg2_str, 16) if isinstance(arg2_str, str) and arg2_str.startswith("0x") else int(arg2_str)
                        except ValueError: pass
                        arg2 = registers.get("RDX", registers.get("EDX", registers.get("RSI", registers.get("ESI", arg2_val))))
                        str_to_print = str_to_print.replace("%d", str(arg2), 1).replace("%i", str(arg2), 1)
                        
                    console_output += str_to_print
                
                # Even if intercepted, we still emulate stack frame
                registers[SP] -= ptr_size
                stack_memory[registers[SP]] = {"val": f"RET {format_rip(pc)}", "comment": "Return Addr"}
                call_stack.append(pc)
                
                if is_intercepted:
                    # Fake the return immediately so we don't jump into un-emulated C internals
                    registers[SP] += ptr_size
                    if registers[SP]-ptr_size in stack_memory: del stack_memory[registers[SP]-ptr_size]
                    call_stack.pop()
                    registers["RAX" if arch == "x64" else "EAX"] = len(str_to_print) if str_to_print != "???" else 0
                    explanation = f"Intercepted runtime library: {cleanup_target}"
                elif target in labels:
                    pc = labels[target]
                    
            elif opcode == "syscall":
                rax = registers.get("RAX", registers.get("EAX", 0))
                if rax == 0: # sys_read
                    fd = registers.get("RDI", registers.get("EDI", 0))
                    buf_addr = registers.get("RSI", registers.get("ESI", 0))
                    length = registers.get("RDX", registers.get("EDX", 0))
                    read_str = stdin_data[:length]
                    stdin_data = stdin_data[length:] # Consume stdin
                    
                    found = False
                    for k, v in data_memory.items():
                        if v["addr"] == buf_addr:
                            v["value"] = read_str
                            found = True
                            break
                    if not found and length > 0:
                        data_memory[f"buf_{hex(buf_addr)}"] = {"addr": buf_addr, "value": read_str, "type": "string"}
                        
                    registers["RAX" if arch == "x64" else "EAX"] = len(read_str)
                    explanation = f"syscall read(fd={fd}, buf={hex(buf_addr)}, len={length}) -> got {len(read_str)} bytes"
                elif rax == 1: # sys_write
                    fd = registers.get("RDI", registers.get("EDI", 0))
                    buf_addr = registers.get("RSI", registers.get("ESI", 0))
                    length = registers.get("RDX", registers.get("EDX", 0))
                    
                    str_out = ""
                    for k, v in data_memory.items():
                        if v["addr"] == buf_addr:
                            str_out = v["value"]
                            break
                    console_output += str_out
                    explanation = f"syscall write(fd={fd}, buf={hex(buf_addr)}, len={length})"
                elif rax == 60: # sys_exit
                    explanation = "syscall exit"
                    break
                else:
                    explanation = f"syscall RAX={rax} (not implemented)"
                    
            elif opcode == "ret":
                bump = ptr_size
                try: 
                    if args.strip(): bump += int(args.strip())
                except: pass
                ret_addr = stack_memory.get(registers[SP], {}).get("val", "")
                if registers[SP] in stack_memory:
                    del stack_memory[registers[SP]]
                registers[SP] += bump
                explanation = f"Returned to caller"
                if call_stack:
                    pc = call_stack.pop()
                else:
                    break 
                    
            elif opcode == "leave":
                registers[SP] = registers[BP]
                val = stack_memory.get(registers[SP], {"val":0})["val"]
                registers[BP] = int(val) if str(val).lstrip('-').isdigit() else val
                if registers[SP] in stack_memory:
                    del stack_memory[registers[SP]]
                registers[SP] += ptr_size
                explanation = "Restored previous stack frame"
                
            elif opcode.startswith("j"):
                target = ops[0]
                jump = False
                if opcode == "jmp": jump = True
                elif opcode in ["je", "jz"] and flags["ZF"] == 1: jump = True
                elif opcode in ["jne", "jnz"] and flags["ZF"] == 0: jump = True
                elif opcode in ["jl", "jnge"] and flags["SF"] != flags["OF"]: jump = True
                elif opcode in ["jle", "jng"] and (flags["ZF"] == 1 or flags["SF"] != flags["OF"]): jump = True
                elif opcode in ["jg", "jnle"] and flags["ZF"] == 0 and flags["SF"] == flags["OF"]: jump = True
                elif opcode in ["jge", "jnl"] and flags["SF"] == flags["OF"]: jump = True
                elif opcode in ["ja", "jnbe"] and flags["CF"] == 0 and flags["ZF"] == 0: jump = True
                elif opcode in ["jae", "jnb"] and flags["CF"] == 0: jump = True
                elif opcode in ["jb", "jnae", "jc"] and flags["CF"] == 1: jump = True
                elif opcode in ["jbe", "jna"] and (flags["CF"] == 1 or flags["ZF"] == 1): jump = True
                
                explanation = f"Jumped to {target}" if jump else f"Did not jump to {target}"
                if jump and target in labels:
                    pc = labels[target]
                
        except Exception as e:
            explanation = f"Error processing instruction: {e}"
            
        registers[IP] = format_rip(pc)
        add_state(original_pc, line, explanation)
        
    return states
