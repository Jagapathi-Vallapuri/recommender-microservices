import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import "./index.css";

function App() {
  const [health, setHealth] = useState({});

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch("http://localhost:8050/service-health");
        const data = await res.json();
        setHealth(data);
      } catch {
        setHealth({});
      }
    };

    fetchHealth();
    const interval = setInterval(fetchHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="container">
      <h1>Microservice Health Dashboard</h1>
      <div className="grid">
        {Object.entries(health).map(([service, status]) => (
          <div key={service} className={`card ${status}`}>
            <h2>{service}</h2>
            <p>Status: {status}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
