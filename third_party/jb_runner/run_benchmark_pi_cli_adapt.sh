#!/usr/bin/env bash
# JobBench runner for PiSubstrate (Pi Coding Agent CLI).
set -euo pipefail

TASKS_BASE_DIR="${TASKS_BASE_DIR:?TASKS_BASE_DIR is required}"
TASK_IDS="${TASK_IDS:?TASK_IDS is required}"
LABEL="${LABEL:?LABEL is required}"
HARNESS_RENDER_DIR="${HARNESS_RENDER_DIR:?HARNESS_RENDER_DIR is required}"
PI_BIN="${SEC_AGENT_HARNESS2_PI_BIN:-${HARNESS2_PI_BIN:-pi}}"
MODEL="${BENCHMARK_MODELS:-gpt-5.4}"
EFFORT="${REASONING_EFFORT:-high}"
TIMEOUT_PER_TASK="${TIMEOUT_PER_TASK:-3600}"

CURRENT_WORK_DIR=""
cleanup() {
    if [ -n "${CURRENT_WORK_DIR}" ] && [ -d "${CURRENT_WORK_DIR}" ]; then
        rm -rf "${CURRENT_WORK_DIR}"
    fi
}
trap cleanup EXIT INT TERM

for TASK_ID in ${TASK_IDS//,/ }; do
    TASK_DIR="${TASKS_BASE_DIR}/${TASK_ID}"
    TASK_SRC_FOLDER="${TASK_DIR}/task_folder"
    OUT_DIR="${TASK_DIR}/model_output/${LABEL}"
    TRAJ_DIR="${TASK_DIR}/model_traj/${LABEL}"

    mkdir -p "${OUT_DIR}" "${TRAJ_DIR}"

    WORK_DIR="$(mktemp -d -t jb_pi_ws_XXXXXX)"
    CURRENT_WORK_DIR="${WORK_DIR}"
    TEMP_TASK_FOLDER="${WORK_DIR}/task_folder"
    TEMP_OUT_DIR="${WORK_DIR}/output"
    mkdir -p "${TEMP_OUT_DIR}"

    if [ -d "${TASK_SRC_FOLDER}" ]; then
        cp -R "${TASK_SRC_FOLDER}" "${TEMP_TASK_FOLDER}"
    else
        mkdir -p "${TEMP_TASK_FOLDER}"
    fi

    for entry in AGENTS.md .pi scripts sub_agents mcp .mcp.json _pi_runtime; do
        if [ -e "${HARNESS_RENDER_DIR}/${entry}" ]; then
            cp -R "${HARNESS_RENDER_DIR}/${entry}" "${WORK_DIR}/${entry}"
        fi
    done

    PROMPT="You are completing a professional work task. All input files for this task are located in the folder below.

=== TASK FOLDER ===
${TEMP_TASK_FOLDER}

=== INSTRUCTIONS ===
1. Read the TASK_INSTRUCTIONS.txt file in the task folder above to understand the full task requirements.
2. Examine all other files in the task folder as needed to complete the task. If a file cannot be read directly (e.g., .xlsx, .docx, .db, .pptx), use appropriate tools, MCP servers, or code to extract and process its contents.
3. Complete the task thoroughly and produce all required deliverables.
4. Only save the final deliverables to the output directory specified below. Do not save any intermediate or temporary files.

=== OUTPUT DIRECTORY ===
Save all final deliverables to: ${TEMP_OUT_DIR}"

    TRAJ_FILE="${TRAJ_DIR}/pi_attempt1.jsonl"

    if [[ "${MODEL}" == *"/"* ]]; then
        PI_PROVIDER="${MODEL%%/*}"
        PI_MODEL_ID="${MODEL#*/}"
    else
        PI_PROVIDER="sec_agent_harness2"
        PI_MODEL_ID="${MODEL}"
    fi

    EXTRA_ARGS=()
    if [ -f "${WORK_DIR}/_pi_runtime/harness2_bridge.ts" ]; then
        EXTRA_ARGS+=("-e" "${WORK_DIR}/_pi_runtime/harness2_bridge.ts")
    fi

    export PI_OFFLINE=1
    export PI_SKIP_VERSION_CHECK=1
    export PI_TELEMETRY=0
    export SEC_AGENT_HARNESS2_PI_HARNESS_DIR="${HARNESS_RENDER_DIR}"
    export SEC_AGENT_HARNESS2_PI_PROVIDER="${PI_PROVIDER}"
    export SEC_AGENT_HARNESS2_PI_ACTIVE_MODEL="${PI_MODEL_ID}"

    (
        cd "${WORK_DIR}"
        "${PI_BIN}" -p "${PROMPT}" \
            --mode json \
            --no-session \
            --tools "read,bash,edit,write,grep,find,ls" \
            --provider "${PI_PROVIDER}" \
            --model "${PI_MODEL_ID}" \
            --thinking "${EFFORT}" \
            "${EXTRA_ARGS[@]}" \
            > "${TRAJ_FILE}"
    )

    if [ -d "${TEMP_OUT_DIR}" ] && [ -n "$(ls -A "${TEMP_OUT_DIR}" 2>/dev/null)" ]; then
        cp -R "${TEMP_OUT_DIR}/." "${OUT_DIR}/"
    fi

    rm -rf "${WORK_DIR}"
    CURRENT_WORK_DIR=""
done
