import { useState } from "react";
import { isLoggedIn, isAdmin, logout } from "./api";
import LoginPage from "./components/LoginPage";
import SearchPage from "./components/SearchPage";
import LibraryPage from "./components/LibraryPage";
import AdminPage from "./components/AdminPage";
import StatusBar from "./components/StatusBar";

type Page = "search" | "library" | "admin";

function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn());
  const [admin, setAdmin] = useState(isAdmin());
  const [page, setPage] = useState<Page>("search");

  const handleLogin = () => {
    setLoggedIn(true);
    setAdmin(isAdmin());
  };

  if (!loggedIn) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">IRC Book Bot</h1>
        <nav className="app-nav">
          <button
            className={page === "search" ? "active" : ""}
            onClick={() => setPage("search")}
          >
            Search
          </button>
          <button
            className={page === "library" ? "active" : ""}
            onClick={() => setPage("library")}
          >
            Library
          </button>
          {admin && (
            <button
              className={page === "admin" ? "active" : ""}
              onClick={() => setPage("admin")}
            >
              Admin
            </button>
          )}
          <button className="btn-logout" onClick={logout}>
            Logout
          </button>
        </nav>
        <StatusBar />
      </header>

      <main className="app-main">
        {page === "search" && <SearchPage />}
        {page === "library" && <LibraryPage />}
        {page === "admin" && admin && <AdminPage />}
      </main>
    </div>
  );
}

export default App;
