#pragma once
#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <functional>
#include <map>

// Real-World Examples: Practical applications of design patterns in actual systems

// ============================================================================
// 1. LOGGING FRAMEWORK (Singleton + Strategy + Chain of Responsibility)
// ============================================================================

enum class LogLevel {
	DEBUG,
	INFO,
	WARNING,
	ERROR,
	FATAL
};

// Strategy Pattern for different log outputs
class LogAppender {
public:
	virtual ~LogAppender() = default;
	virtual void Append(LogLevel level, const std::string& message) = 0;
};

class ConsoleAppender : public LogAppender {
public:
	void Append(LogLevel level, const std::string& message) override {
		std::cout << "[CONSOLE] " << message << "\n";
	}
};

class FileAppender : public LogAppender {
private:
	std::string filename;

public:
	explicit FileAppender(const std::string& file) : filename(file) {}

	void Append(LogLevel level, const std::string& message) override {
		std::cout << "[FILE:" << filename << "] " << message << "\n";
		// In real implementation: write to file
	}
};

// Chain of Responsibility for log filtering
class LogFilter {
private:
	LogFilter* next;
	LogLevel minLevel;

public:
	explicit LogFilter(LogLevel level) : next(nullptr), minLevel(level) {}

	void SetNext(LogFilter* nextFilter) {
		next = nextFilter;
	}

	bool ShouldLog(LogLevel level) {
		if (level >= minLevel) {
			return true;
		}
		if (next) {
			return next->ShouldLog(level);
		}
		return false;
	}
};

// Singleton Logger
class Logger {
private:
	std::vector<LogAppender*> appenders;
	LogLevel minLevel;

	Logger() : minLevel(LogLevel::INFO) {}

public:
	static Logger& GetInstance() {
		static Logger instance;
		return instance;
	}

	Logger(const Logger&) = delete;
	Logger& operator=(const Logger&) = delete;

	void AddAppender(LogAppender* appender) {
		appenders.push_back(appender);
	}

	void SetMinLevel(LogLevel level) {
		minLevel = level;
	}

	void Log(LogLevel level, const std::string& message) {
		if (level < minLevel) return;

		for (auto* appender : appenders) {
			appender->Append(level, message);
		}
	}

	void Debug(const std::string& msg) { Log(LogLevel::DEBUG, "DEBUG: " + msg); }
	void Info(const std::string& msg) { Log(LogLevel::INFO, "INFO: " + msg); }
	void Warning(const std::string& msg) { Log(LogLevel::WARNING, "WARNING: " + msg); }
	void Error(const std::string& msg) { Log(LogLevel::ERROR, "ERROR: " + msg); }
};

// ============================================================================
// 2. HTTP CLIENT (Facade + Proxy + Builder)
// ============================================================================

// Complex subsystem
class HTTPConnection {
public:
	void Open(const std::string& url) {
		std::cout << "Opening connection to " << url << "\n";
	}

	void SetHeader(const std::string& key, const std::string& value) {
		std::cout << "Setting header: " << key << " = " << value << "\n";
	}

	void Send(const std::string& body) {
		std::cout << "Sending: " << body << "\n";
	}

	std::string Receive() {
		return "{\"status\": \"ok\"}";
	}

	void Close() {
		std::cout << "Closing connection\n";
	}
};

// Builder Pattern for request construction
class HTTPRequest {
	friend class Builder;

private:
	std::string url;
	std::string method;
	std::map<std::string, std::string> headers;
	std::string body;

public:
	HTTPRequest() = default;

	std::string GetURL() const { return url; }
	std::string GetMethod() const { return method; }
	const std::map<std::string, std::string>& GetHeaders() const { return headers; }
	std::string GetBody() const { return body; }

	// Builder class defined after HTTPRequest is complete
	class Builder;
};

// Builder implementation outside the class
class HTTPRequest::Builder {
private:
	std::string url;
	std::string method;
	std::map<std::string, std::string> headers;
	std::string body;

public:
	Builder() = default;

	Builder& SetURL(const std::string& u) {
		url = u;
		return *this;
	}

	Builder& SetMethod(const std::string& m) {
		method = m;
		return *this;
	}

	Builder& AddHeader(const std::string& key, const std::string& value) {
		headers[key] = value;
		return *this;
	}

	Builder& SetBody(const std::string& b) {
		body = b;
		return *this;
	}

	HTTPRequest Build() {
		HTTPRequest request;
		request.url = url;
		request.method = method;
		request.headers = headers;
		request.body = body;
		return request;
	}
};

// Facade Pattern - simplified interface
class HTTPClient {
public:
	virtual ~HTTPClient() = default;

	virtual std::string Get(const std::string& url) {
		HTTPConnection conn;
		conn.Open(url);
		conn.SetHeader("Method", "GET");
		conn.Send("");
		std::string response = conn.Receive();
		conn.Close();
		return response;
	}

	virtual std::string Post(const std::string& url, const std::string& data) {
		HTTPConnection conn;
		conn.Open(url);
		conn.SetHeader("Method", "POST");
		conn.SetHeader("Content-Type", "application/json");
		conn.Send(data);
		std::string response = conn.Receive();
		conn.Close();
		return response;
	}
};

// Proxy Pattern - adds caching
class CachedHTTPClient : public HTTPClient {
private:
	std::map<std::string, std::string> cache;

public:
	std::string Get(const std::string& url) override {
		if (cache.find(url) != cache.end()) {
			std::cout << "Returning cached response\n";
			return cache[url];
		}

		std::string response = HTTPClient::Get(url);
		cache[url] = response;
		return response;
	}
};

// ============================================================================
// 3. DATABASE CONNECTION POOL (Object Pool + Singleton)
// ============================================================================

class DatabaseConnection {
private:
	int id;
	bool inUse;

public:
	explicit DatabaseConnection(int connId) : id(connId), inUse(false) {
		std::cout << "Creating DB connection " << id << "\n";
	}

	void Execute(const std::string& query) {
		std::cout << "Connection " << id << " executing: " << query << "\n";
	}

	void SetInUse(bool use) { inUse = use; }
	bool IsInUse() const { return inUse; }
	int GetID() const { return id; }
};

// Object Pool Pattern
class ConnectionPool {
private:
	std::vector<DatabaseConnection*> connections;
	static constexpr int POOL_SIZE = 5;

	ConnectionPool() {
		for (int i = 0; i < POOL_SIZE; i++) {
			connections.push_back(new DatabaseConnection(i));
		}
	}

public:
	static ConnectionPool& GetInstance() {
		static ConnectionPool instance;
		return instance;
	}

	~ConnectionPool() {
		for (auto* conn : connections) {
			delete conn;
		}
	}

	DatabaseConnection* AcquireConnection() {
		for (auto* conn : connections) {
			if (!conn->IsInUse()) {
				conn->SetInUse(true);
				std::cout << "Acquired connection " << conn->GetID() << "\n";
				return conn;
			}
		}
		std::cout << "No available connections!\n";
		return nullptr;
	}

	void ReleaseConnection(DatabaseConnection* conn) {
		if (conn) {
			conn->SetInUse(false);
			std::cout << "Released connection " << conn->GetID() << "\n";
		}
	}
};

// RAII wrapper for automatic release
class ConnectionGuard {
private:
	DatabaseConnection* conn;

public:
	explicit ConnectionGuard(DatabaseConnection* c) : conn(c) {}

	~ConnectionGuard() {
		ConnectionPool::GetInstance().ReleaseConnection(conn);
	}

	DatabaseConnection* Get() { return conn; }
};

// ============================================================================
// 4. PLUGIN SYSTEM (Factory + Strategy + Observer)
// ============================================================================

// Plugin interface (Strategy)
class Plugin {
public:
	virtual ~Plugin() = default;
	virtual std::string GetName() const = 0;
	virtual void Initialize() = 0;
	virtual void Execute() = 0;
	virtual void Shutdown() = 0;
};

// Concrete plugins
class ImageProcessorPlugin : public Plugin {
public:
	std::string GetName() const override { return "ImageProcessor"; }

	void Initialize() override {
		std::cout << "ImageProcessor plugin initialized\n";
	}

	void Execute() override {
		std::cout << "Processing images...\n";
	}

	void Shutdown() override {
		std::cout << "ImageProcessor plugin shutdown\n";
	}
};

class DataExporterPlugin : public Plugin {
public:
	std::string GetName() const override { return "DataExporter"; }

	void Initialize() override {
		std::cout << "DataExporter plugin initialized\n";
	}

	void Execute() override {
		std::cout << "Exporting data...\n";
	}

	void Shutdown() override {
		std::cout << "DataExporter plugin shutdown\n";
	}
};

// Plugin Factory
class PluginFactory {
private:
	std::map<std::string, std::function<Plugin*()>> creators;

public:
	void RegisterPlugin(const std::string& name, std::function<Plugin*()> creator) {
		creators[name] = creator;
		std::cout << "Registered plugin: " << name << "\n";
	}

	Plugin* CreatePlugin(const std::string& name) {
		if (creators.find(name) != creators.end()) {
			return creators[name]();
		}
		return nullptr;
	}

	std::vector<std::string> GetAvailablePlugins() const {
		std::vector<std::string> names;
		for (const auto& pair : creators) {
			names.push_back(pair.first);
		}
		return names;
	}
};

// Plugin Manager (Facade)
class PluginManager {
private:
	PluginFactory factory;
	std::vector<Plugin*> loadedPlugins;

public:
	~PluginManager() {
		for (auto* plugin : loadedPlugins) {
			plugin->Shutdown();
			delete plugin;
		}
	}

	void RegisterPlugin(const std::string& name, std::function<Plugin*()> creator) {
		factory.RegisterPlugin(name, creator);
	}

	void LoadPlugin(const std::string& name) {
		Plugin* plugin = factory.CreatePlugin(name);
		if (plugin) {
			plugin->Initialize();
			loadedPlugins.push_back(plugin);
			std::cout << "Loaded plugin: " << name << "\n";
		}
	}

	void ExecuteAll() {
		for (auto* plugin : loadedPlugins) {
			plugin->Execute();
		}
	}
};

// ============================================================================
// 5. EVENT SYSTEM (Observer + Command)
// ============================================================================

// Event data
struct Event {
	std::string type;
	std::string data;
};

// Observer
class EventListener {
public:
	virtual ~EventListener() = default;
	virtual void OnEvent(const Event& event) = 0;
};

// Event Dispatcher
class EventDispatcher {
private:
	std::map<std::string, std::vector<EventListener*>> listeners;

public:
	void Subscribe(const std::string& eventType, EventListener* listener) {
		listeners[eventType].push_back(listener);
	}

	void Dispatch(const Event& event) {
		if (listeners.find(event.type) != listeners.end()) {
			for (auto* listener : listeners[event.type]) {
				listener->OnEvent(event);
			}
		}
	}
};

// Concrete listeners
class UIListener : public EventListener {
public:
	void OnEvent(const Event& event) override {
		std::cout << "[UI] Received event: " << event.type << " - " << event.data << "\n";
	}
};

class LoggingListener : public EventListener {
public:
	void OnEvent(const Event& event) override {
		std::cout << "[LOG] Event logged: " << event.type << "\n";
	}
};

// Usage examples
inline void RealWorldExamplesDemo() {
	std::cout << "=== 1. Logging Framework ===\n";
	Logger& logger = Logger::GetInstance();
	logger.AddAppender(new ConsoleAppender());
	logger.AddAppender(new FileAppender("app.log"));
	logger.Info("Application started");
	logger.Warning("Low memory warning");
	logger.Error("Connection failed");

	std::cout << "\n=== 2. HTTP Client ===\n";
	HTTPRequest request = HTTPRequest::Builder()
		.SetURL("https://api.example.com")
		.SetMethod("POST")
		.AddHeader("Authorization", "Bearer token123")
		.SetBody("{\"data\": \"example\"}")
		.Build();

	CachedHTTPClient client;
	client.Get("https://example.com");
	client.Get("https://example.com");  // Cached

	std::cout << "\n=== 3. Connection Pool ===\n";
	ConnectionPool& pool = ConnectionPool::GetInstance();
	{
		ConnectionGuard conn1(pool.AcquireConnection());
		ConnectionGuard conn2(pool.AcquireConnection());
		if (conn1.Get()) conn1.Get()->Execute("SELECT * FROM users");
		if (conn2.Get()) conn2.Get()->Execute("INSERT INTO logs VALUES (...)");
	}  // Connections auto-released

	std::cout << "\n=== 4. Plugin System ===\n";
	PluginManager pluginMgr;
	pluginMgr.RegisterPlugin("ImageProcessor", []() { return new ImageProcessorPlugin(); });
	pluginMgr.RegisterPlugin("DataExporter", []() { return new DataExporterPlugin(); });
	pluginMgr.LoadPlugin("ImageProcessor");
	pluginMgr.LoadPlugin("DataExporter");
	pluginMgr.ExecuteAll();

	std::cout << "\n=== 5. Event System ===\n";
	EventDispatcher dispatcher;
	UIListener uiListener;
	LoggingListener logListener;

	dispatcher.Subscribe("user_login", &uiListener);
	dispatcher.Subscribe("user_login", &logListener);

	Event loginEvent{"user_login", "user123"};
	dispatcher.Dispatch(loginEvent);
}

// These examples demonstrate:
// 1. How patterns work together in real systems
// 2. Practical applications beyond textbook examples
// 3. Common architectural patterns in production code
// 4. How patterns solve actual software engineering problems
//
// Key takeaways:
// - Patterns are tools, not goals
// - Combine patterns to solve complex problems
// - Keep it simple - don't over-engineer
// - Patterns emerge from refactoring, not upfront design
