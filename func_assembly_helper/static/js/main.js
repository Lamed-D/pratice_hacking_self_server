document.addEventListener('DOMContentLoaded', () => {
    const btnCompile = document.getElementById('btn-compile');
    const sourceEditorDiv = document.getElementById('source-editor');
    const asmViewer = document.getElementById('assembly-view');
    const btnReset = document.getElementById('btn-reset');
    const btnRestart = document.getElementById('btn-restart');
    const btnPrev = document.getElementById('btn-prev');
    const btnStep = document.getElementById('btn-step');
    const btnPlay = document.getElementById('btn-play');
    
    const modeSelect = document.getElementById('mode-select');
    const sourcePanelHeader = document.getElementById('source-panel-header');
    const speedSlider = document.getElementById('speed-slider');
    const liveTooltip = document.getElementById('live-tooltip');
    const consoleOutput = document.getElementById('console-output');
    const cppContainer = document.getElementById('cpp-container');
    const rawAsmEditor = document.getElementById('raw-asm-editor');
    const btnFormat = document.getElementById('btn-format');
    const timelineSlider = document.getElementById('timeline-slider');
    const btnHexToggle = document.getElementById('btn-hex-toggle');
    const stdinInput = document.getElementById('stdin-input');
    
    let useHex = true;

    btnHexToggle.addEventListener('click', () => {
        useHex = !useHex;
        btnHexToggle.innerText = useHex ? "HEX" : "DEC";
        if (simulationStates.length > 0 && currentStateIndex >= 0) {
            renderState(simulationStates[currentStateIndex]);
        }
    });
    
    // Initialize Ace Editor
    let editor = null;
    let activeLineMarker = null;
    
    if (window.ace && sourceEditorDiv) {
        editor = ace.edit("source-editor");
        editor.setTheme("ace/theme/tomorrow_night_eighties");
        editor.session.setMode("ace/mode/c_cpp");
        editor.setOptions({
            fontSize: "14px",
            fontFamily: "var(--font-mono)",
            showPrintMargin: false,
            wrap: true
        });
    }
    
    if (btnFormat && editor) {
        btnFormat.addEventListener('click', () => {
            const beautify = ace.require("ace/ext/beautify");
            beautify.beautify(editor.session);
        });
    }
    
    const tabStack = document.getElementById('tab-stack');
    const tabData = document.getElementById('tab-data');
    const stackContainer = document.getElementById('stack-container');
    const dataContainer = document.getElementById('data-container');
    const dataView = document.getElementById('data-view');
    
    let simulationStates = [];
    let currentStateIndex = -1;
    let playInterval = null;
    let isPlaying = false;
    
    function stopPlay() {
        if (playInterval) clearInterval(playInterval);
        playInterval = null;
        isPlaying = false;
        btnPlay.innerText = "▶ Play";
    }

    const modal = document.getElementById("cheatsheet-modal");
    const btnCheat = document.getElementById("btn-cheatsheet");
    const spanClose = document.getElementsByClassName("close-btn")[0];
    btnCheat.onclick = () => modal.style.display = "block";
    spanClose.onclick = () => modal.style.display = "none";
    window.onclick = (e) => { if (e.target == modal) modal.style.display = "none"; };

    const compilerSelect = document.getElementById('compiler-select');

    // Tabs logic
    const tabMmap = document.getElementById('tab-mmap');
    const mmapContainer = document.getElementById('mmap-container');
    
    tabStack.addEventListener('click', () => {
        tabStack.classList.add('active'); tabData.classList.remove('active'); tabMmap.classList.remove('active');
        stackContainer.style.display = 'flex'; dataContainer.style.display = 'none'; mmapContainer.style.display = 'none';
    });
    tabData.addEventListener('click', () => {
        tabData.classList.add('active'); tabStack.classList.remove('active'); tabMmap.classList.remove('active');
        dataContainer.style.display = 'flex'; stackContainer.style.display = 'none'; mmapContainer.style.display = 'none';
    });
    tabMmap.addEventListener('click', () => {
        tabMmap.classList.add('active'); tabStack.classList.remove('active'); tabData.classList.remove('active');
        mmapContainer.style.display = 'flex'; stackContainer.style.display = 'none'; dataContainer.style.display = 'none';
    });

    modeSelect.addEventListener('change', () => {
        if (modeSelect.value === 'asm') {
            cppContainer.style.display = 'none';
            rawAsmEditor.style.display = 'block';
            compilerSelect.disabled = true;
            btnCompile.innerText = "Simulate Code";
            asmViewer.innerHTML = "<div class='empty-state'>Assembly execution ready. Click Simulate.</div>";
        } else {
            cppContainer.style.display = 'flex';
            rawAsmEditor.style.display = 'none';
            compilerSelect.disabled = false;
            btnCompile.innerText = "Compile & Load";
            asmViewer.innerHTML = "<div class='empty-state'>Click 'Compile & Load' to see assembly.</div>";
        }
    });

    const OPCODE_MANUAL = {
        "mov": "Copies data from source to destination.",
        "lea": "Load Effective Address. Calculates memory address and stores it.",
        "push": "Decrements stack pointer and stores data on the stack.",
        "pop": "Loads data from the stack and increments stack pointer.",
        "add": "Adds source to destination.",
        "sub": "Subtracts source from destination.",
        "call": "Pushes return address and jumps to function.",
        "ret": "Pops return address and jumps to it.",
        "syscall": "Invokes operating system kernel function.",
        "cmp": "Compares source and destination, updates flags.",
        "je": "Jump if Equal (ZF=1).",
        "jmp": "Unconditional Jump.",
        "xor": "Bitwise exclusive OR. Often used to zero a register.",
        "leave": "Restores previous stack frame (mov esp, ebp; pop ebp)."
    };

    // Breakpoints logic removed per user request

    btnCompile.addEventListener('click', async () => {
        const mode = modeSelect.value;
        const compiler = compilerSelect.value;
        btnCompile.disabled = true;
        btnCompile.innerText = mode === 'cpp' ? "Compiling..." : "Processing...";
        asmViewer.innerHTML = "<div class='empty-state'>Processing...</div>";
        liveTooltip.innerText = "Simulation not started.";
        consoleOutput.innerText = "";
        
        try {
            const endpoint = mode === 'cpp' ? '/api/compile_and_simulate' : '/api/simulate_only';
            const sourceCode = editor ? editor.getValue() : sourceEditorDiv.innerText;
            const payload = mode === 'cpp' 
                ? { code: sourceCode, options: '-O0', compiler: compiler, stdin: stdinInput.value }
                : { assembly: rawAsmEditor.value, arch: compiler.includes('x86') ? 'x86' : 'x64', stdin: stdinInput.value };
                
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            
            if (!res.ok) {
                asmViewer.innerHTML = `<div class='empty-state' style='color: var(--danger)'>${data.error || 'Compilation Error'}</div>`;
            } else {
                // Parse and display assembly text by lines for highlighting
                let asmText = mode === 'cpp' ? data.assembly : rawAsmEditor.value;
                asmText = (asmText || "").replace(/;\s*##LINE:\d+/g, "");
                
                if (mode === 'cpp') rawAsmEditor.value = asmText;
                
                const lines = asmText.split('\n');
                let asmHtml = '';
                lines.forEach((line, index) => {
                    let text = line.replace(/</g, "&lt;");
                    // Opcode tooltipping
                    if (text.trim() && !text.includes(':') && !text.startsWith('.')) {
                        const parts = text.trim().split(/\s+/);
                        const op = parts[0].toLowerCase();
                        if (OPCODE_MANUAL[op]) {
                            text = text.replace(parts[0], `<span class="opcode-tooltip" title="${OPCODE_MANUAL[op]}">${parts[0]}</span>`);
                        }
                    }
                    asmHtml += `<div id="asm-line-${index}" class="asm-line">${text}</div>`;
                });
                asmViewer.innerHTML = asmHtml;
                
                // Initialize states
                simulationStates = data.states;
                currentStateIndex = 0;
                
                // Enable controls
                btnStep.disabled = false;
                btnRestart.disabled = false;
                btnPlay.disabled = false;
                btnPrev.disabled = true;
                
                timelineSlider.max = simulationStates.length - 1;
                timelineSlider.value = 0;
                timelineSlider.disabled = false;
                
                stopPlay();
                
                renderState(simulationStates[currentStateIndex]);
            }
        } catch (e) {
            asmViewer.innerHTML = `<div class='empty-state' style='color: var(--danger)'>Network Error: ${e.message}</div>`;
        } finally {
            btnCompile.disabled = false;
            btnCompile.innerText = modeSelect.value === 'cpp' ? "Compile & Load" : "Simulate Code";
        }
    });
    
    let prevState = null;
    
    function highlightCppLine(lineNum) {
        if (!editor || !lineNum) return;
        if (activeLineMarker !== null) {
            editor.session.removeMarker(activeLineMarker);
            activeLineMarker = null;
        }
        const Range = ace.require('ace/range').Range;
        activeLineMarker = editor.session.addMarker(new Range(lineNum - 1, 0, lineNum - 1, 1), "active-cpp-line", "fullLine");
        editor.scrollToLine(lineNum - 1, true, true, function () {});
    }

    function formatValue(val) {
        if (!val && val !== 0) return val;
        if (typeof val === 'string' && val.includes('+') && isNaN(parseInt(val))) return val; 
        
        let parsed = parseInt(val);
        if (isNaN(parsed)) return val;
        // Verify it isn't just a string blending numbers
        if (typeof val === 'string' && !val.startsWith('0x') && !/^-?\d+$/.test(val)) return val;

        if (useHex) {
            if (parsed < 0) return "-0x" + Math.abs(parsed).toString(16);
            return "0x" + parsed.toString(16);
        } else {
            return parsed.toString();
        }
    }

    function renderState(state) {
        if (!state) return;
        
        // Render Tooltip and Console Output
        if (state.explanation) liveTooltip.innerText = state.explanation;
        if (state.console_output !== undefined) {
             consoleOutput.innerText = state.console_output;
             consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }
        
        // Render Flags
        if (state.flags) {
            const flagsView = document.getElementById('flags-view');
            if (flagsView) {
                let fHtml = '';
                for (const [f, v] of Object.entries(state.flags)) {
                    fHtml += `<div><span style="color:var(--text-muted); font-size:0.85em; font-family:var(--font-mono); margin-right:4px;">${f}</span><span style="font-family:var(--font-mono); font-weight:bold; color:${v ? 'var(--danger)' : 'var(--success)'}">${v}</span></div>`;
                }
                flagsView.innerHTML = fHtml;
            }
        }
        
        // Render Registers
        const regList = document.getElementById('register-list');
        let regHtml = `<div style="padding: 16px; display: grid; gap: 8px;">`;
        for (const [reg, val] of Object.entries(state.registers)) {
            let cls = '';
            if (prevState && formatValue(prevState.registers[reg]) !== formatValue(val)) {
                cls = 'flash-write';
            }
            regHtml += `<div class="${cls}" style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border); padding-bottom:4px; transition: background 0.3s;">
                <span style="color:var(--accent); font-weight:bold; font-family:var(--font-mono)">${reg}</span>
                <span style="font-family:var(--font-mono);">${formatValue(val)}</span>
            </div>`;
        }
        regHtml += `</div>`;
        regList.innerHTML = regHtml;
               // Render Stack
        const stackList = document.getElementById('stack-view');
        let stackHtml = `<div style="padding: 16px; display: grid; gap: 8px;">`;
        
        const base_ptr = parseInt(state.registers.RBP || state.registers.EBP || state.registers.BP || "0", 16);
        const stack_ptr = parseInt(state.registers.RSP || state.registers.ESP || state.registers.SP || "0", 16);
        
        for (const frame of state.stack) {
            let cls = '';
            const frameAddr = parseInt(frame.address, 16);
            
            let frameLabel = '';
            if (base_ptr && stack_ptr && frameAddr <= base_ptr && frameAddr >= stack_ptr) {
                cls += ' current-frame';
                if (frameAddr === base_ptr) frameLabel = '<span title="Base Pointer" style="color:var(--danger); font-size:10px; padding:0 4px; border:1px solid var(--danger); border-radius:4px; margin-right:4px;">BP</span>';
                if (frameAddr === stack_ptr) frameLabel += '<span title="Stack Pointer" style="color:var(--success); font-size:10px; padding:0 4px; border:1px solid var(--success); border-radius:4px; margin-right:4px;">SP</span>';
            } else if (base_ptr && frameAddr > base_ptr) {
                cls += ' caller-frame';
            }
            
            // Basic simplistic change detection
            if (prevState) {
                const prevFrame = prevState.stack.find(f => f.address === frame.address);
                if (!prevFrame || prevFrame.value !== frame.value) cls += ' flash-write';
            }
            stackHtml += `<div class="${cls.trim()}" style="border:1px solid var(--border); border-radius:4px; padding:6px 8px; display:flex; justify-content:space-between; align-items:center; gap:8px;">
                <span style="color:var(--text-muted); font-family:var(--font-mono); font-size: 0.75em; flex: 0 0 auto;">${frameLabel}${formatValue(frame.address)}</span>
                <span style="font-family:var(--font-mono); font-weight:600; flex: 1 1 auto; text-align:center; word-break:break-all; font-size: 0.85em;">${formatValue(frame.value)}</span>
                <span style="color:var(--text-muted); font-size: 0.75em; flex: 0 0 auto; text-align:right;">${frame.comment || ''}</span>
            </div>`;
        }
        stackHtml += `</div>`;
        stackList.innerHTML = stackHtml;

        // Render Data Segment
        if (state.data) {
            let dataHtml = `<div style="display: flex; flex-direction: column; gap: 8px;">`;
            for (const [lbl, info] of Object.entries(state.data)) {
                 dataHtml += `<div style="border:1px solid var(--border); border-radius:4px; padding:6px 8px;">
                    <div style="color:var(--text-muted); font-size: 0.75em; font-family:var(--font-mono)">${lbl} (${hexFormat(info.addr)})</div>
                    <div style="font-family:var(--font-mono); font-size: 0.85em; color:var(--success); margin-top:4px;">${info.type === 'string' ? '"' + info.value + '"' : info.value}</div>
                 </div>`;
            }
            dataHtml += `</div>`;
            if (Object.keys(state.data).length === 0) dataHtml = `<div class="empty-state">No data segments found.</div>`;
            dataView.innerHTML = dataHtml;
        }

        // Render Memory Map
        if (state.stack || state.data) {
            const mmView = document.getElementById('mmap-view');
            let mmapHtml = `<div style="color:var(--accent); margin-bottom: 8px;">[STACK SEGMENT]</div>`;
            for(const f of state.stack) {
                 mmapHtml += `<div>${formatValue(f.address)} : <span style="color:#fff">${formatValue(f.value)}</span> <span style="color:var(--text-muted)">; ${f.comment}</span></div>`;
            }
            mmapHtml += `<br><div style="color:var(--success); margin-bottom: 8px;">[DATA SEGMENT]</div>`;
            if(Object.keys(state.data).length === 0) mmapHtml += `<div class="empty-state">Empty</div>`;
            for(const [lbl, info] of Object.entries(state.data)) {
                 mmapHtml += `<div>${formatValue(info.addr)} : <span style="color:#fff">${String(info.value).replace(/\\n/g, '<br>')}</span> <span style="color:var(--text-muted)">; ${lbl} (${info.type})</span></div>`;
            }
            mmView.innerHTML = mmapHtml;
        }

        // Highlight Active Line
        document.querySelectorAll('.asm-line').forEach(el => el.classList.remove('active-line'));
        if (state.line !== -1) {
            const activeEl = document.getElementById(`asm-line-${state.line}`);
            if (activeEl) {
                activeEl.classList.add('active-line');
                activeEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
        
        // Highlight C++ Source if mapped
        if (state.cpp_line) {
            highlightCppLine(state.cpp_line);
        } else if (editor && activeLineMarker) {
            editor.session.removeMarker(activeLineMarker);
            activeLineMarker = null;
        }

        prevState = state;
    }
    
    function hexFormat(val) {
        return "0x" + val.toString(16);
    }
    
    btnStep.addEventListener('click', () => {
        if (currentStateIndex < simulationStates.length - 1) {
            currentStateIndex++;
            timelineSlider.value = currentStateIndex;
            renderState(simulationStates[currentStateIndex]);
        }
        btnPrev.disabled = (currentStateIndex === 0);
        btnStep.disabled = (currentStateIndex >= simulationStates.length - 1);
    });

    btnPrev.addEventListener('click', () => {
        if (currentStateIndex > 0) {
            currentStateIndex--;
            timelineSlider.value = currentStateIndex;
            renderState(simulationStates[currentStateIndex]);
        }
        btnPrev.disabled = (currentStateIndex === 0);
        btnStep.disabled = (currentStateIndex >= simulationStates.length - 1);
        btnPlay.disabled = false;
    });

    timelineSlider.addEventListener('input', (e) => {
        currentStateIndex = parseInt(e.target.value);
        renderState(simulationStates[currentStateIndex]);
        btnPrev.disabled = (currentStateIndex === 0);
        btnStep.disabled = (currentStateIndex >= simulationStates.length - 1);
        btnPlay.disabled = (currentStateIndex >= simulationStates.length - 1);
    });

    btnReset.addEventListener('click', () => {
        location.reload();
    });

    btnRestart.addEventListener('click', () => {
        stopPlay();
        currentStateIndex = 0;
        timelineSlider.value = 0;
        renderState(simulationStates[currentStateIndex]);
        btnStep.disabled = false;
        btnPlay.disabled = false;
        btnPrev.disabled = true;
        
        // Scroll asmViewer back to top
        asmViewer.scrollTop = 0;
    });

    btnPlay.addEventListener('click', () => {
        if (isPlaying) {
            stopPlay();
        } else {
            if (currentStateIndex >= simulationStates.length - 1) return;
            isPlaying = true;
            btnPlay.innerText = "⏸ Pause";
            
            // read speed from slider
            const speedMs = parseInt(speedSlider.max) - parseInt(speedSlider.value) + parseInt(speedSlider.min);
            
            playInterval = setInterval(() => {
                if (currentStateIndex < simulationStates.length - 1) {
                    currentStateIndex++;
                    timelineSlider.value = currentStateIndex;
                    renderState(simulationStates[currentStateIndex]);
                    btnPrev.disabled = false;
                } else {
                    stopPlay();
                    btnStep.disabled = true;
                    btnPlay.disabled = true;
                }
            }, speedMs);
        }
    });
});
