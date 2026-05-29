"use client";

import { useState } from "react";

export default function Home() {

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedFileName, setSelectedFileName] = useState("");

  const [uploadMessage, setUploadMessage] = useState("");

  const uploadFile = async () => {

    if (!selectedFile) {
      setUploadMessage("Please select a PDF file.");
      return;
    }

    const formData = new FormData();

    formData.append(
      "file",
      selectedFile
    );

    try {

      const response = await fetch(
        "http://127.0.0.1:8000/upload",
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      setUploadMessage(`✅ ${selectedFile.name} uploaded successfully`);

    } catch (error) {

      console.error(error);

      setUploadMessage(
        "Upload failed."
      );
    }
  };

  const processDocuments = async () => {

    try {

      const response = await fetch(
        "http://127.0.0.1:8000/process",
        {
          method: "POST",
        }
      );

      const data = await response.json();

      setUploadMessage(
        `✅ Knowledge Base Updated
          📄 ${data.pages} pages processed

          🧩 ${data.chunks} chunks created
          🤖 Ready for questions`
      );

    } catch (error) {

      console.error(error);

      setUploadMessage(
        "Processing failed."
      );
    }
  };

  const askQuestion = async () => {

    if (!question.trim()) return;

    const currentQuestion = question;

    const userMessage = {
      role: "user",
      content: currentQuestion,
    };

    setMessages((prev) => [
      ...prev,
      userMessage
    ]);

    setQuestion("");
    setLoading(true);

    try {

      const response = await fetch(
        "http://127.0.0.1:8000/ask",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question: currentQuestion,
          }),
        }
      );

      const data = await response.json();

      const botMessage = {
        role: "assistant",
        content: data.answer,
      };

      setMessages((prev) => [
        ...prev,
        botMessage
      ]);

    } catch (error) {

      console.error(error);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Unable to connect to backend.",
        },
      ]);
    }

    setLoading(false);
  };

  const handleKeyDown = (e) => {

    if (
      e.key === "Enter" &&
      !e.shiftKey
    ) {
      e.preventDefault();
      askQuestion();
    }
  };

  return (
    <main className="min-h-screen bg-gray-950 text-white">

      <div className="max-w-6xl mx-auto p-6">

        <h1 className="text-5xl font-bold mb-3">
          Field Service Report Assistant
        </h1>

        <p className="text-gray-300 text-lg mb-6">
          Ask questions about SOPs, PPE requirements,
          telecom tower guidelines, safety policies
          and compliance procedures.
        </p>

        {/* Upload Section */}

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">

          <h2 className="text-xl font-semibold mb-4">
            Upload Policy Documents
          </h2>

          <input
            type="file"
            accept=".pdf"
            onChange={(e) => {
              setSelectedFile(e.target.files[0]);

              if (e.target.files[0]) {
                setSelectedFileName(
                  e.target.files[0].name
              );
            }
          }}
          className="mb-4"
        />
        {selectedFileName && (
          <p className="text-gray-300 mb-4">
            📄 Selected: {selectedFileName}
          </p>
        )}
          <div className="flex gap-4">

            <button
              onClick={uploadFile}
              className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg"
            >
              Upload PDF
            </button>

            <button
              onClick={processDocuments}
              className="bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg"
            >
              Process Documents
            </button>

          </div>

          {uploadMessage && (

            <p className="mt-4 text-green-400 whitespace-pre-line">
              {uploadMessage}
            </p>

          )}

        </div>

        {/* Chat Area */}

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 min-h-[500px]">

          {messages.length === 0 && (

            <div className="text-gray-400 text-center mt-24">

              <h2 className="text-2xl mb-4">
                Start a conversation
              </h2>

              <p>
                Example:
              </p>

              <ul className="mt-4 space-y-2">

                <li>
                  • What PPE requirements are mentioned?
                </li>

                <li>
                  • When should respiratory protection be used?
                </li>

                <li>
                  • What telecom tower safety guidelines exist?
                </li>

              </ul>

            </div>

          )}

          <div className="space-y-4">

            {messages.map((msg, index) => (

              <div
                key={index}
                className={`p-4 rounded-xl max-w-[85%] ${
                  msg.role === "user"
                    ? "bg-blue-600 ml-auto text-white"
                    : "bg-gray-800 text-white"
                }`}
              >

                <div className="font-semibold mb-2">

                  {msg.role === "user"
                    ? "You"
                    : "Field Service Assistant"}

                </div>

                <div className="whitespace-pre-wrap">

                  {msg.content}

                </div>

              </div>

            ))}

            {loading && (

              <div className="bg-gray-800 p-4 rounded-xl max-w-[85%]">

                <div className="font-semibold mb-2">
                  Field Service Assistant
                </div>

                <div>
                  Thinking...
                </div>

              </div>

            )}

          </div>

        </div>

        {/* Input */}

        <div className="mt-6">

          <textarea
            className="w-full p-4 rounded-xl bg-gray-900 border border-gray-700 text-white"
            rows={4}
            placeholder="Ask a question about policies, SOPs, PPE requirements, telecom tower guidelines..."
            value={question}
            onChange={(e) =>
              setQuestion(e.target.value)
            }
            onKeyDown={handleKeyDown}
          />

          <div className="flex justify-end mt-4">

            <button
              onClick={askQuestion}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-semibold"
            >
              {loading
                ? "Thinking..."
                : "Ask Question"}
            </button>

          </div>

        </div>

      </div>

    </main>
  );
}