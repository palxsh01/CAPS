import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { FileText, Mic, User, UserX, Shield, Send, MessageSquare, Wallet } from "lucide-react";
import { VoiceOrb } from "./components/VoiceOrb";
import { AIProcessCloud } from "./components/AIProcessCloud";
import { DecisionButtons } from "./components/DecisionButtons";
import { LogsPanel } from "./components/LogsPanel";
import { LogEntry } from "./components/LogCard";
import { DelayedPaymentTimer } from "./components/DelayedPaymentTimer";
import { useVoiceInput } from "../hooks/useVoiceInput";
import { processCommand, CommandResponse, getUserState, UserState, executeApproved } from "../api/client";
import { ScammerPanel } from "./components/ScammerPanel";
import { TransactionHistoryPanel } from "./components/TransactionHistoryPanel";

type AppState =
  | "idle"
  | "listening"
  | "processing"
  | "understanding"
  | "evaluating"
  | "checking"
  | "deciding"
  | "awaiting"
  | "executing"
  | "completed"
  | "blocked"
  | "error";

interface DelayedPayment {
  id: string;
  amount: string;
  recipient: string;
  delayedUntil: Date;
  intent: any; // Store the intent for delayed execution
}

export default function App() {
  const [state, setState] = useState<AppState>("idle");
  const [messages, setMessages] = useState<string[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logsOpen, setLogsOpen] = useState(false);
  const [delayedPayment, setDelayedPayment] = useState<DelayedPayment | null>(null);
  const [pendingApproval, setPendingApproval] = useState<CommandResponse | null>(null);
  const [scammerPanelOpen, setScammerPanelOpen] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [textInput, setTextInput] = useState("");
  const textInputRef = useRef<HTMLInputElement>(null);
  const [userState, setUserState] = useState<UserState | null>(null);
  const [historyPanelOpen, setHistoryPanelOpen] = useState(false);

  // Fetch initial user state on mount
  useEffect(() => {
    getUserState().then(setUserState).catch(console.error);
  }, []);

  // Real Voice Input Hook
  const { isListening, transcript, startListening, stopListening } = useVoiceInput();

  // Effect to handle listening state changes
  useEffect(() => {
    if (isListening) {
      if (state !== "listening") setState("listening");
      if (transcript) setMessages([transcript]); // Show what is being heard
    } else if (state === "listening") {
      // Stopped listening, now processing
      handleVoiceEnd();
    }
  }, [isListening, transcript]);

  const startVoiceInput = () => {
    if (state !== "idle" && state !== "completed" && state !== "error") return;
    setMessages(["Listening..."]);
    startListening();
  };

  const handleTextSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const input = textInput.trim();
    if (!input) return;
    if (state !== "idle" && state !== "completed" && state !== "error") return;

    setTextInput("");
    setState("processing");
    setMessages([`Processing: "${input}"`]);

    await new Promise(r => setTimeout(r, 500));

    try {
      setState("understanding");
      setMessages(["Interpreting command...", `Input: ${input}`]);

      const result = await processCommand(input);
      processBackendResult(result);
    } catch (e) {
      console.error(e);
      setState("error");
      setMessages(["Error connecting to server.", "Please try again."]);
      setTimeout(() => setState("idle"), 3000);
    }
  };

  const handleVoiceEnd = async () => {
    if (!transcript.trim()) {
      setState("idle");
      setMessages([]);
      return;
    }

    setState("processing");
    setMessages(["Processing audio...", `Heard: "${transcript}"`]);

    // Artificial delay for UX (to show processing state)
    await new Promise(r => setTimeout(r, 800));

    try {
      setState("understanding");
      setMessages(["Interpreting command...", `Input: ${transcript}`]);

      const result = await processCommand(transcript);

      // Map backend result to UI state
      processBackendResult(result);

    } catch (e) {
      console.error(e);
      setState("error");
      setMessages(["Error connecting to server.", "Please try again."]);
      setTimeout(() => setState("idle"), 3000);
    }
  };

  const processBackendResult = async (result: CommandResponse) => {
    const intentType = result.intent?.intent_type;

    // Handle Balance Inquiry - Text Only Response
    if (intentType === 'BALANCE_INQUIRY' && result.execution_result) {
      updateUserState(result);
      setState("evaluating");
      setMessages([
        `Your current balance is ₹${result.execution_result.balance}.`,
        `Today's spending: ₹${result.execution_result.daily_spend} of ₹${result.execution_result.daily_limit || 2000} daily limit.`
      ]);

      setTimeout(() => {
        setState("completed");
        setTimeout(() => setState("idle"), 2000);
      }, 6000);
      return;
    }

    // Handle Transaction History - Text Only Response
    if (intentType === 'TRANSACTION_HISTORY' && result.execution_result?.history) {
      updateUserState(result);
      setState("evaluating");
      const historyMsgs = result.execution_result.history.length === 0
        ? ["No recent transactions found."]
        : [
          "Your recent transactions:",
          // @ts-ignore
          ...result.execution_result.history.slice(0, 4).map((txn: any) =>
            `• ₹${txn.amount} to ${txn.merchant_vpa} (${new Date(txn.timestamp).toLocaleDateString()})`
          )
        ];
      setMessages(historyMsgs);

      setTimeout(() => {
        setState("completed");
        setTimeout(() => setState("idle"), 2000);
      }, 9000);
      return;
    }

    // ─── FULL 6-STAGE CAPS PIPELINE (For Payments) ─────────────────

    const steps: string[] = [];

    // Stage 1: Session Memory — Resolve references
    setState("evaluating");
    if (result.context_used && (result.context_used.merchant_vpa || result.context_used.amount)) {
      steps.push("🧠 [Memory] Resolving references...");
      if (result.context_used.merchant_vpa)
        steps.push(`   → merchant: ${result.context_used.merchant_vpa}`);
      if (result.context_used.amount)
        steps.push(`   → amount: ₹${result.context_used.amount}`);
    } else {
      steps.push("🧠 [Memory] No references to resolve");
    }
    setMessages([...steps]);
    await new Promise(r => setTimeout(r, 600));

    // Stage 2: LLM Intent Interpretation
    steps.push(`🤖 [LLM] Intent: ${result.intent?.intent_type}`);
    steps.push(`   Confidence: ${((result.intent?.confidence_score || 0) * 100).toFixed(0)}%`);
    if (result.intent?.amount) steps.push(`   Amount: ₹${result.intent.amount}`);
    if (result.intent?.merchant_vpa) steps.push(`   Merchant: ${result.intent.merchant_vpa}`);
    setMessages([...steps]);
    await new Promise(r => setTimeout(r, 600));

    // Stage 3: Schema Validation (Trust Gate 1)
    setState("checking");
    if (result.status === 'error' && result.message?.includes("couldn't understand")) {
      steps.push("🔒 [Trust Gate 1] Schema Validation ✗");
      steps.push(`   ${result.message}`);
      setMessages([...steps]);
      setState("blocked");
      completeTransaction(result, "declined");
      return;
    }
    steps.push("🔒 [Trust Gate 1] Schema Validation ✓");
    setMessages([...steps]);
    await new Promise(r => setTimeout(r, 500));

    // Stage 4: Context + Fraud Intelligence
    steps.push("🌐 [Context] User & merchant data fetched");
    if (result.user_state) {
      steps.push(`   Balance: ₹${result.user_state.balance} | Spend: ₹${result.user_state.daily_spend}`);
    }

    // Fraud Intel display
    if (result.fraud_intel) {
      const fi = result.fraud_intel;
      steps.push(`🛡️ [Fraud Intel] ${fi.badge_emoji} ${fi.badge} (${fi.total_reports} reports, ${fi.scam_rate}% scam)`);
    }
    setMessages([...steps]);
    await new Promise(r => setTimeout(r, 600));

    // Check for fraud-blocked status
    if (result.status === 'blocked' && result.fraud_intel) {
      setState("blocked");
      steps.push(`🚫 BLOCKED: ${result.fraud_intel.badge_emoji} ${result.message}`);
      setMessages([...steps]);
      completeTransaction(result, "declined");
      return;
    }

    // Stage 5: Policy Evaluation (Trust Gate 2)
    setState("deciding");
    steps.push(`🔐 [Trust Gate 2] Policy: ${result.policy_decision}`);
    steps.push(`   Risk Score: ${result.risk_info?.score ?? 'N/A'}`);
    if (result.risk_info?.violations && result.risk_info.violations.length > 0) {
      steps.push(`   ⚠ ${result.risk_info.violations.length} violation(s)`);
    } else {
      steps.push("   No policy violations");
    }
    setMessages([...steps]);
    await new Promise(r => setTimeout(r, 600));

    // Stage 6: Execution / Decision Routing
    if (result.policy_decision === "APPROVE") {
      if (isBusy) {
        // Delayed Payment Logic
        handleBusyDelay(result);
      } else {
        setState("executing");
        steps.push("💸 [Execution] Processing payment...");
        setMessages([...steps]);
        await new Promise(r => setTimeout(r, 800));

        completeTransaction(result, "approved");
      }
    } else if (result.policy_decision === "DENY") {
      setState("blocked");
      steps.push(`🚫 [Denied] ${result.risk_info?.reason || result.message}`);
      setMessages([...steps]);
      completeTransaction(result, "declined");
    } else {
      // COOLDOWN or ESCALATE -> Ask user
      setState("awaiting");
      setPendingApproval(result); // Store pending result for approval
      steps.push("⏳ [Escalated] Manual approval required");
      setMessages([...steps]);
    }
  };

  // Helper: update user state from any backend response
  const updateUserState = (result: CommandResponse) => {
    if (result.user_state) {
      setUserState(prev => ({
        ...prev,
        balance: result.user_state!.balance,
        daily_spend: result.user_state!.daily_spend,
        daily_limit: result.user_state!.daily_limit,
        trust_score: result.user_state!.trust_score,
        recent_transactions: result.user_state!.recent_transactions || prev?.recent_transactions || [],
      }));
    }
  };

  const completeTransaction = (result: CommandResponse, decision: "approved" | "declined") => {
    // Update persisted user state
    updateUserState(result);
    // Create Log Entry
    const newLog: LogEntry = {
      id: Date.now().toString(),
      timestamp: new Date(),
      command: result.intent?.raw_input || "",
      amount: result.intent?.amount?.toString() || "0",
      recipient: result.intent?.merchant_vpa || "Unknown",
      description: result.intent?.intent_type || "Transaction",
      confidence: Number((result.intent?.confidence_score || 0) * 100),
      context: [`Risk: ${result.risk_info?.score}`, `Conf: ${((result.intent?.confidence_score || 0) * 100).toFixed(0)}%`],
      policyChecks: result.risk_info?.violations || [],
      decision: decision,
      steps: [`Result: ${result.status}`, `Ref: ${result.execution_result?.reference_number || 'N/A'}`],
    };

    setLogs(prev => [newLog, ...prev]);

    if (decision === "approved") {
      setState("completed");
    }

    setTimeout(() => {
      setState("idle");
      setMessages([]);
    }, 3000);
  };

  const handleBusyDelay = (result: CommandResponse) => {
    const delayedUntil = new Date();
    delayedUntil.setSeconds(delayedUntil.getSeconds() + 30);

    setDelayedPayment({
      id: Date.now().toString(),
      amount: result.intent?.amount?.toString() || "0",
      recipient: result.intent?.merchant_vpa || "Unknown",
      delayedUntil,
      intent: result.intent,
    });

    setState("completed");
    setMessages(["User busy. Payment delayed 30s."]);
    setTimeout(() => {
      setState("idle");
      setMessages([]);
    }, 2000);
  };

  const handleApprove = async () => {
    if (!pendingApproval || !pendingApproval.intent) {
      setState("idle");
      return;
    }

    setState("executing");
    setMessages(prev => [...prev, "👤 User confirmed. Executing..."]);

    try {
      // Call backend to execute the approved transaction
      const rawInput = pendingApproval.intent.raw_input || "";
      const mpva = pendingApproval.intent.merchant_vpa || "";
      const amount = pendingApproval.intent.amount || 0;

      const result = await executeApproved(mpva, amount, rawInput);

      // Complete transaction (logs, state update, UI completion)
      completeTransaction(result, "approved");
    } catch (e) {
      console.error("Execution failed", e);
      setState("error");
      setMessages(["Execution failed."]);
      setTimeout(() => setState("idle"), 2000);
    } finally {
      setPendingApproval(null);
    }
  };

  const handleDecline = () => {
    setState("blocked");
    setPendingApproval(null);
    setTimeout(() => setState("idle"), 2000);
  };

  const handleWait = () => {
    // Similar to busy delay
    setState("idle");
  };

  const handleDelayedTimeUp = () => {
    // Execute the delayed payment
    if (delayedPayment) {
      setState("executing");
      setMessages(["Executing delayed payment..."]);
      setTimeout(() => {
        setState("completed");
        setDelayedPayment(null);
        setTimeout(() => setState("idle"), 2000);
      }, 1500);
    }
  };

  const handleCancelDelayed = () => {
    setDelayedPayment(null);
  };


  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-black text-white relative overflow-hidden">
      {/* Backgrounds */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-purple-900/20 via-transparent to-transparent pointer-events-none" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,_var(--tw-gradient-stops))] from-blue-900/10 via-transparent to-transparent pointer-events-none" />

      {/* Delayed Payment Timer */}
      <AnimatePresence>
        {delayedPayment && (
          <DelayedPaymentTimer
            payment={delayedPayment}
            onCancel={handleCancelDelayed}
            onTimeUp={handleDelayedTimeUp}
          />
        )}
      </AnimatePresence>

      {/* Scammer Panel Toggle */}
      <motion.button
        onClick={() => setScammerPanelOpen(true)}
        className="absolute top-6 left-6 z-30 w-12 h-12 rounded-full bg-white/5 backdrop-blur-xl border border-white/10 flex items-center justify-center hover:bg-red-500/10 hover:border-red-500/20 transition-all group"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
      >
        <Shield className="w-5 h-5 text-white/60 group-hover:text-red-400 transition-colors" />
      </motion.button>

      {/* Busy Mode Toggle */}
      <motion.div
        className="absolute top-6 left-1/2 -translate-x-1/2 z-30"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <button
          onClick={() => setIsBusy(!isBusy)}
          className={`px-4 py-2 rounded-full backdrop-blur-xl border transition-all flex items-center gap-2 ${isBusy
            ? "bg-yellow-500/20 border-yellow-500/30 text-yellow-300"
            : "bg-white/5 border-white/10 text-white/60 hover:bg-white/10"
            }`}
        >
          {isBusy ? (
            <>
              <UserX className="w-4 h-4" />
              <span className="text-xs font-medium">Busy Mode</span>
            </>
          ) : (
            <>
              <User className="w-4 h-4" />
              <span className="text-xs font-light">Available</span>
            </>
          )}
        </button>
      </motion.div>

      {/* Balance Bar — tap to open history */}
      {userState && (
        <motion.div
          className="absolute top-20 left-1/2 -translate-x-1/2 z-30 cursor-pointer"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          onClick={() => setHistoryPanelOpen(true)}
        >
          <div className="flex items-center gap-4 px-5 py-2.5 rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 hover:bg-white/8 transition-all">
            <div className="flex items-center gap-2">
              <Wallet className="w-4 h-4 text-emerald-400" />
              <span className="text-sm font-semibold text-emerald-300">₹{userState.balance.toLocaleString()}</span>
            </div>
            <div className="w-px h-4 bg-white/10" />
            <div className="text-xs text-white/40">
              <span>Spent: ₹{userState.daily_spend}</span>
              <span className="mx-1">/</span>
              <span>₹{userState.daily_limit}</span>
            </div>
            <div className="w-px h-4 bg-white/10" />
            <div className="text-xs text-white/40">
              Trust: {(userState.trust_score * 100).toFixed(0)}%
            </div>
          </div>
        </motion.div>
      )}

      {/* Logs Toggle */}
      <motion.button
        onClick={() => setLogsOpen(true)}
        className="absolute top-6 right-6 z-30 w-12 h-12 rounded-full bg-white/5 backdrop-blur-xl border border-white/10 flex items-center justify-center hover:bg-white/10 transition-all group"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        <FileText className="w-5 h-5 text-white/60 group-hover:text-white/90 transition-colors" />
        {logs.length > 0 && (
          <motion.div
            className="absolute -top-1 -right-1 w-5 h-5 bg-purple-500 rounded-full flex items-center justify-center text-xs font-medium"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
          >
            {logs.length}
          </motion.div>
        )}
      </motion.button>

      {/* Main Interface */}
      <div className="relative z-10 min-h-screen flex flex-col items-center justify-center px-6 py-12 gap-12">
        {/* Voice Orb */}
        <div
          onClick={state === "idle" || state === "completed" || state === "error" ? startVoiceInput : undefined}
          className={state === "idle" || state === "completed" || state === "error" ? "cursor-pointer" : ""}
        >
          <VoiceOrb state={state} />
        </div>

        {/* AI Cloud Messages */}
        <div className="w-full max-w-md">
          <AIProcessCloud messages={messages} isStreaming={state !== "idle" && state !== "completed"} />
        </div>

        {/* Buttons */}
        <DecisionButtons
          show={state === "awaiting"}
          onApprove={handleApprove}
          onWait={handleWait}
          onDecline={handleDecline}
        />

        {/* Text Input Bar */}
        <motion.div
          className="fixed bottom-0 left-0 right-0 z-40 p-4 bg-gradient-to-t from-gray-950 via-gray-950/95 to-transparent"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <form
            onSubmit={handleTextSubmit}
            className="max-w-lg mx-auto flex items-center gap-3"
          >
            <div className="flex-1 relative">
              <MessageSquare className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
              <input
                ref={textInputRef}
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Type a command... e.g. 'pay 500 to shop@upi'"
                disabled={state !== "idle" && state !== "completed" && state !== "error"}
                className="w-full pl-10 pr-4 py-3 bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-purple-500/40 focus:bg-white/8 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              />
            </div>
            <motion.button
              type="submit"
              disabled={(state !== "idle" && state !== "completed" && state !== "error") || !textInput.trim()}
              className="w-11 h-11 rounded-xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-300 hover:bg-purple-500/30 hover:text-purple-200 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <Send className="w-4 h-4" />
            </motion.button>
          </form>
          <div className="max-w-lg mx-auto mt-2 flex items-center justify-center gap-4">
            <div className="flex items-center gap-1.5 text-white/20">
              <Mic className="w-3 h-3" />
              <span className="text-[10px]">Tap orb to speak</span>
            </div>
            <span className="text-white/10 text-[10px]">•</span>
            <span className="text-[10px] text-white/20">Real Transactions Enabled</span>
          </div>
        </motion.div>
      </div>

      <LogsPanel logs={logs} isOpen={logsOpen} onClose={() => setLogsOpen(false)} />
      <ScammerPanel isOpen={scammerPanelOpen} onClose={() => setScammerPanelOpen(false)} />
      <TransactionHistoryPanel
        isOpen={historyPanelOpen}
        onClose={() => setHistoryPanelOpen(false)}
        transactions={userState?.recent_transactions || []}
        balance={userState?.balance || 0}
        dailySpend={userState?.daily_spend || 0}
        dailyLimit={userState?.daily_limit || 2000}
      />
    </div>
  );
}
