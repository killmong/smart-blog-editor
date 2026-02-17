import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import { useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import { Toaster } from "react-hot-toast";
import Header from "./components/layout/Header";
import Editor from "./components/Editor";
import Login from "./components/auth/Login";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { useEditorStore } from "./store/useEditorStore";
import { useAutoSave } from "./hooks/useAutoSave";
import { useAuthStore } from "./store/authStore";
import Signup from "./components/auth/Signup";
import "./App.css";
const EditorPage = () => {
  const { title, setTitle } = useEditorStore();
  const { id, setId } = useEditorStore();

  useEffect(() => {
    if (!id) {
      setId(uuidv4()); 
    }
  }, [id, setId]);
  useAutoSave();

  return (
    <>
      <Toaster position="top-center" reverseOrder={false} />
      <Header />
      <main className="max-w-4xl mx-auto mt-12 px-4">
        <input
          type="text"
          placeholder="Untitled Post"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full text-5xl font-extrabold text-gray-900 placeholder-gray-300 outline-none bg-transparent mb-8 leading-tight tracking-tight"
        />
        <Editor />
      </main>
    </>
  );
};

function App() {
  const { isAuthenticated } = useAuthStore();

  return (
    <Router>
      <div className="min-h-screen bg-[#F9F9FB] text-gray-900 font-sans pb-20">
        <Routes>
          <Route
            path="/signup"
            element={!isAuthenticated ? <Signup /> : <Navigate to="/editor" />}
          />{" "}
          <Route
            path="/login"
            element={!isAuthenticated ? <Login /> : <Navigate to="/editor" />}
          />
          <Route
            path="/editor"
            element={
              <ProtectedRoute>
                <EditorPage />
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<Navigate to="/editor" />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
