import React, { useState } from "react";
import axios from "axios";

export default function App() {
  const primaryColor = "#1ABC9C"; // new main color (teal)
  const secondaryColor = "#FF6B6B"; // accent color (coral)
  const lightBg = "#FDF6F0"; // light card background
  const darkBg = "#3E2C1C"; // dark chocolate background

  const [page, setPage] = useState("login");
  const [user, setUser] = useState(null);
  const [form, setForm] = useState({
    roomType: "Bedroom",
    belief: "Vastu",
    length: "",
    width: "",
    notes: "",
  });
  const [imagePreview, setImagePreview] = useState(null);
  const [result, setResult] = useState(null);
  const [feedback, setFeedback] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [showGuide, setShowGuide] = useState(false);

  // -------- Input Handlers --------
  function handleInputChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  function handleFileChange(e) {
    const file = e.target.files[0];
    if (file) setImagePreview(URL.createObjectURL(file));
  }

  // -------- Mock Processing --------
 async function startProcessing() {
  if (!form.roomType || !form.belief || !form.length || !form.width) {
    alert("Please fill all required fields before generating layout!");
    setPage("input");
    return;
  }

  setPage("processing");
  setResult(null);
  setAccepted(false);

  try {
    const formData = new FormData();
    formData.append("roomType", form.roomType);
    formData.append("belief", form.belief);
    formData.append("length", form.length);
    formData.append("width", form.width);
    formData.append("notes", form.notes);

    const fileInput = document.querySelector("input[type='file']");
    if (fileInput && fileInput.files[0]) {
      formData.append("image", fileInput.files[0]);
    }

    const res = await axios.post(
      "http://localhost:5000/generate",
      formData
    );

    setResult(res.data);
    setPage("output");

  } catch (error) {
    console.error(error);
    alert("Error connecting to backend");
    setPage("input");
  }
}

  // -------- Login --------
  function handleLogin(e) {
    e.preventDefault();
    const email = e.target.email.value.trim();
    const password = e.target.password.value.trim();

    if (!email || !password) {
      alert("Please fill in both fields");
      return;
    }

    setUser({ email });
    setPage("home");
  }

  return (
    <div className="min-h-screen" style={{ background: darkBg }}>
      {/* -------- HEADER -------- */}
      <header className="shadow-sm bg-white">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              style={{ background: primaryColor }}
              className="w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold"
            >
              AI
            </div>
            <h1 className="text-lg font-semibold">
              AI-Based Interior Design Optimizer
            </h1>
          </div>

          {user && (
            <button
              onClick={() => {
                setUser(null);
                setPage("login");
              }}
              className="text-sm text-gray-600 hover:underline"
            >
              Logout
            </button>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-12">
        {/* -------- LOGIN PAGE -------- */}
        {page === "login" && (
          <section className="min-h-screen flex items-center justify-center">
            <div
              className="bg-[#FDF6F0] rounded-3xl p-10 shadow-2xl max-w-md w-full animate-fadeIn"
            >
              <h2
                className="text-3xl font-bold mb-6 text-center text-[#4B334C]"
              >
                User Login
              </h2>
              <form onSubmit={handleLogin} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium mb-1 text-gray-700">
                    Email
                  </label>
                  <input
                    type="email"
                    name="email"
                    className="w-full p-4 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#1ABC9C] placeholder-gray-400"
                    placeholder="Enter your email"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1 text-gray-700">
                    Password
                  </label>
                  <input
                    type="password"
                    name="password"
                    className="w-full p-4 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#1ABC9C] placeholder-gray-400"
                    placeholder="Enter password"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full py-4 rounded-xl font-bold text-white bg-gradient-to-r from-[#1ABC9C] to-[#FF6B6B] shadow-lg hover:scale-105 transition-transform"
                >
                  Login
                </button>
              </form>

              
            </div>
          </section>
        )}

        {/* -------- HOME PAGE -------- */}
        {page === "home" && user && (
          <section
            className="bg-gradient-to-r from-[#E0F7F4] to-[#FFE5E5] rounded-3xl p-12 shadow-xl flex flex-col md:flex-row items-center gap-10 animate-fadeIn"
          >
            <div className="flex-1">
              <h2 className="text-4xl font-extrabold mb-4 text-[#1ABC9C]">
                Welcome {user.email}
              </h2>
              <p className="text-gray-700 mb-6">
                Start designing your room layout powered by AI-based suggestions.
              </p>
              <div className="flex gap-4">
                <button
                  onClick={() => setPage("input")}
                  className="px-7 py-4 rounded-full bg-gradient-to-r from-[#1ABC9C] to-[#FF6B6B] font-bold text-white hover:scale-105 transition-transform"
                >
                  Get Started
                </button>
                <button
                  onClick={() => setShowGuide(true)}
                  className="px-6 py-4 rounded-full border border-gray-400 text-gray-700 hover:bg-gray-100 transition-all"
                >
                  How it works
                </button>
              </div>
            </div>
          </section>
        )}

        {/* -------- INPUT PAGE -------- */}
        {page === "input" && (
          <section className="bg-gradient-to-b from-[#F0FDF9] to-[#FFF5F5] rounded-3xl p-10 shadow-xl animate-fadeIn">
            <h3 className="text-2xl font-bold mb-6 text-[#bc1ab9]">
              Room Details & Inputs
            </h3>
            <div className="space-y-3">
              <label className="block text-sm font-medium">Room Type</label>
              <select
                name="roomType"
                value={form.roomType}
                onChange={handleInputChange}
                className="w-full p-3 rounded-lg border focus:outline-none focus:ring-2 focus:ring-[#1ABC9C]"
              >
                <option>Bedroom</option>
                <option>Living Room</option>
                <option>Kitchen</option>
                <option>Study</option>
              </select>

              <label className="block text-sm font-medium">
                Religious Belief / Directional Preference
              </label>
              <select
                name="belief"
                value={form.belief}
                onChange={handleInputChange}
                className="w-full p-3 rounded-lg border focus:outline-none focus:ring-2 focus:ring-[#1ABC9C]"
              >
                <option>Vastu</option>
              
                <option>None</option>
              </select>

              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-sm font-medium">Length (m)</label>
                  <input
                    name="length"
                    value={form.length}
                    onChange={handleInputChange}
                    className="w-full p-3 rounded-lg border focus:ring-2 focus:ring-[#1ABC9C]"
                    placeholder="e.g. 4"
                  />
                </div>
                <div className="flex-1">
                  <label className="block text-sm font-medium">Width (m)</label>
                  <input
                    name="width"
                    value={form.width}
                    onChange={handleInputChange}
                    className="w-full p-3 rounded-lg border focus:ring-2 focus:ring-[#1ABC9C]"
                    placeholder="e.g. 3"
                  />
                </div>
              </div>

              <label className="block text-sm font-medium">Additional Notes</label>
              <textarea
                name="notes"
                value={form.notes}
                onChange={handleInputChange}
                className="w-full p-3 rounded-lg border focus:ring-2 focus:ring-[#1ABC9C]"
                placeholder="e.g. Window on East wall"
              />

              <div>
                <label className="block text-sm font-medium mb-2">
                  Upload Room Image (optional)
                </label>
                <input type="file" accept="image/*" onChange={handleFileChange} />
                {imagePreview && (
                  <img
                    src={imagePreview}
                    alt="preview"
                    className="mt-3 w-48 h-32 object-cover rounded-md shadow-sm"
                  />
                )}
              </div>

              <div className="flex gap-3 mt-4">
                <button
                  onClick={startProcessing}
                  className="px-5 py-3 rounded-full font-medium shadow transition-all duration-300 hover:scale-105"
                  style={{ background: primaryColor, color: "white" }}
                >
                  Generate Layout
                </button>

                <button
                  onClick={() => setPage("home")}
                  className="px-4 py-3 rounded-full border transition-all duration-300 hover:bg-gray-50"
                >
                  Back
                </button>
              </div>
            </div>
          </section>
        )}

        {/* -------- PROCESSING PAGE -------- */}
        {page === "processing" && (
          <section className="bg-gradient-to-r from-[#1ABC9C] to-[#FF6B6B] rounded-3xl p-12 shadow-xl flex flex-col items-center animate-pulse">
            <div className="w-24 h-24 border-4 border-white border-t-transparent rounded-full animate-spin mb-4"></div>
            <h3 className="text-xl font-bold text-white mb-2">Optimizing layout...</h3>
            <p className="text-white text-center">
              AI is analyzing your inputs. Please wait...
            </p>
          </section>
        )}

        {/* -------- OUTPUT PAGE -------- */}
        {page === "output" && result && (
          <section className="bg-gradient-to-r from-[#E0F7F4] to-[#FFF5F5] rounded-3xl p-8 shadow-xl">
            <h3 className="text-2xl font-semibold mb-2 text-[#1ABC9C]">{result.title}</h3>
            <p className="text-gray-700 mb-4">{result.summary}</p>

            <div className="space-y-3 mb-4">
              {result.layoutHints.map((h, i) => (
                <div
                  key={i}
                  className="p-4 rounded-2xl border-l-4 border-[#1ABC9C] bg-gradient-to-r from-[#D0F2EB] to-[#FFE5E5] shadow-lg flex items-start gap-3"
                >
                  <div
                    className="w-3 h-3 rounded-full mt-2"
                    style={{ background: primaryColor }}
                  ></div>
                  <div className="text-sm font-medium">{h}</div>
                </div>
              ))}
            </div>

            <label className="block text-sm font-medium mb-2">Your feedback</label>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              className="w-full p-3 rounded-lg border focus:ring-2 focus:ring-[#1ABC9C]"
              placeholder="Tell us what should change..."
            />

            <div className="flex gap-3 mt-4">
              <button
                onClick={() => {
                  if (!feedback) {
                    alert("Please enter feedback before re-processing.");
                    return;
                  }
                  startProcessing();
                }}
                className="px-5 py-3 rounded-full font-medium shadow transition-all duration-300 hover:scale-105"
                style={{ background: primaryColor, color: "white" }}
              >
                Re-process
              </button>

              <button
                onClick={() => {
                  setAccepted(true);
                  setPage("home");
                  alert("Layout accepted. Returning to home page.");
                }}
                className="px-5 py-3 rounded-full border transition-all duration-300 hover:bg-gray-50"
              >
                Accept & Continue
              </button>
            </div>
          </section>
        )}
      </main>

      

      {/* -------- HOW IT WORKS MODAL -------- */}
      {showGuide && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 animate-fadeIn">
          <div className="bg-white rounded-2xl p-6 w-96 shadow-lg transform transition-all duration-300 scale-100 hover:scale-[1.02]">
            <h3 className="text-xl font-semibold mb-3 text-[#1ABC9C]">
              How It Works
            </h3>
            <ol className="list-decimal list-inside text-gray-700 space-y-2 text-sm">
              <li>Login to your account to begin.</li>
              <li>Enter your room details such as size and belief system.</li>
              <li>Upload a room image (optional) to assist AI analysis.</li>
              <li>AI generates layout suggestions based on your inputs.</li>
              <li>Review, give feedback, or accept the final design.</li>
            </ol>
            <button
              onClick={() => setShowGuide(false)}
              className="mt-5 w-full py-2 rounded-lg text-white font-medium transition-all duration-300 hover:opacity-90"
              style={{ background: primaryColor }}
            >
              Got it
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
