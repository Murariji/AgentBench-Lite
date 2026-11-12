PHASE 3 NOTES - LLM LAYER
AgentBench-Lite | completed 2026-11-12
=====================================================================

Goal: connect the "brain". One standard port (LLMClient), two plugs:
FakeLLM (tests) and GeminiClient (real, free tier).

First real run (gemini-3.5-flash-lite):
    USER   : What is 15% of 840?
    GEMINI : tool request -> calculator {'expression': '0.15 * 840'}   tokens 217/22
    TOOL   : 126                       (OUR code ran it, not Gemini)
    GEMINI : 15% of 840 is 126.                                       tokens 253/14


=====================================================================
PART 1 - CORE CONCEPTS
=====================================================================

LLM API         Gemini runs on Google's servers. We send an HTTPS request
                (key in a header, JSON body) and get JSON back.
No memory       Every request starts from zero, so we resend the WHOLE
                conversation (the "messages") each time. That's why the
                2nd request had more input tokens (253 vs 217).
Tool calling    The model only ASKS for a tool (ToolRequest). Our code
                runs it (ToolRegistry.execute) and sends the result back.
                The tool menu = each Tool's name/description/parameters.
Tokens          ~3/4 of a word. Input = everything we send (incl. the
                tool menu - that's why even a short question was 217).
                Output = what the model writes (incl. hidden "thinking").
Thought signature
                Newer Gemini models attach a hidden code to tool requests
                that must be sent back unchanged. Stored in
                ToolRequest.provider_data so the rest of the code never
                has to know about it.


=====================================================================
PART 2 - FILES (src/agentbench/llm/)
=====================================================================

base.py    Message      one chat entry: user / assistant / tool
           ToolRequest  the model asking for a tool
           LLMResponse  one reply: text and/or tool request + tokens
           LLMClient    the port: generate(messages, tools, system_prompt)
           LLMError     ONE error type for every provider problem
fake.py    FakeLLM      scripted replies; records what it received
gemini.py  GeminiClient the ONLY file that imports Google's SDK.
                        Translator: ours <-> Gemini's format
                        ("assistant" <-> "model", tool result ->
                        function_response, thinking parts skipped)


=====================================================================
PART 3 - API KEYS & SECURITY
=====================================================================

API key       like a hotel key card: whoever holds it can use your quota
.env          real key, on your laptop only (in .gitignore)
.env.example  template with a fake value, committed to GitHub
$env:X=...    lives only in ONE terminal until it closes
python-dotenv copies .env into the environment when a script starts
Leaked key?   delete it in AI Studio immediately; git history never forgets
Checks        git check-ignore .env   -> prints .env
              git status              -> must NOT list .env
Budget        free tier only, billing disabled -> no charges possible


=====================================================================
PART 4 - ERRORS WE MET (and what they taught)
=====================================================================

401 UNAUTHENTICATED   key rejected (new "AQ." key issue) -> new key fixed it
503 high demand       Google's side overloaded -> switched to Flash-Lite
Rule: 4xx = OUR side (fix the request; 429 = slow down)
      5xx = THEIR side (retry later)
Phase 4 will retry 429/503 automatically but NOT 401.


=====================================================================
PART 5 - TESTS
=====================================================================

test_llm.py     data rules + FakeLLM (no SDK needed)
test_gemini.py  translation code with hand-built Gemini objects;
                no network, no key; skipped if SDK not installed
Result: 49 passed.


=====================================================================
PART 6 - SELF-CHECK
=====================================================================

1. Who runs the calculator: Gemini or our code?
2. Why did the 2nd request use more input tokens than the 1st?
3. Why is gemini.py the only file that imports Google's SDK?
4. Why do tests use FakeLLM instead of real Gemini? (give 3 reasons)
5. 401 vs 503: whose problem is each, and should we retry?
