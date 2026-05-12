#pragma once
#include <iostream>
#include <string>
#include <memory>
#include <chrono>
#include <thread>

namespace proxy_pattern {
// Proxy Pattern: Provides a surrogate or placeholder for another object to control access to it.

// Types of Proxies:
// 1. Remote Proxy - represents object in different address space
// 2. Virtual Proxy - creates expensive objects on demand
// 3. Protection Proxy - controls access to original object
// 4. Smart Reference - performs additional actions when object is accessed

// Subject interface
class Image {
public:
	virtual ~Image() = default;
	virtual void Display() = 0;
	virtual int GetWidth() const = 0;
	virtual int GetHeight() const = 0;
};

// Real Subject - actual image
class RealImage : public Image {
private:
	std::string filename;
	int width;
	int height;

	void LoadFromDisk() {
		std::cout << "Loading " << filename << " from disk...\n";
		// Simulate expensive loading operation
		std::this_thread::sleep_for(std::chrono::seconds(2));
		// Simulate reading dimensions
		width = 1920;
		height = 1080;
		std::cout << "Loaded " << filename << "\n";
	}

public:
	explicit RealImage(const std::string& file) : filename(file), width(0), height(0) {
		LoadFromDisk();
	}

	void Display() override {
		std::cout << "Displaying " << filename << " (" << width << "x" << height << ")\n";
	}

	int GetWidth() const override { return width; }
	int GetHeight() const override { return height; }
};

// Virtual Proxy - delays creation of expensive object
class ImageProxy : public Image {
private:
	std::string filename;
	mutable RealImage* realImage;
	int width;  // Cached dimensions
	int height;

public:
	explicit ImageProxy(const std::string& file)
		: filename(file), realImage(nullptr), width(0), height(0) {
		// Don't load image yet - just store filename
		std::cout << "ImageProxy created for " << filename << "\n";
	}

	~ImageProxy() {
		delete realImage;
	}

	void Display() override {
		if (realImage == nullptr) {
			realImage = new RealImage(filename);
		}
		realImage->Display();
	}

	int GetWidth() const override {
		if (realImage != nullptr) {
			return realImage->GetWidth();
		}
		return width;
	}

	int GetHeight() const override {
		if (realImage != nullptr) {
			return realImage->GetHeight();
		}
		return height;
	}
};

// Protection Proxy Example
enum class AccessLevel {
	READ_ONLY,
	READ_WRITE,
	ADMIN
};

class Document {
public:
	virtual ~Document() = default;
	virtual void Read() = 0;
	virtual void Write(const std::string& content) = 0;
	virtual void Delete() = 0;
};

class RealDocument : public Document {
private:
	std::string content;

public:
	void Read() override {
		std::cout << "Reading document: " << content << "\n";
	}

	void Write(const std::string& newContent) override {
		content = newContent;
		std::cout << "Writing to document: " << content << "\n";
	}

	void Delete() override {
		std::cout << "Deleting document\n";
		content = "";
	}
};

class ProtectionProxy : public Document {
private:
	RealDocument* realDocument;
	AccessLevel accessLevel;

public:
	ProtectionProxy(RealDocument* doc, AccessLevel level)
		: realDocument(doc), accessLevel(level) {}

	~ProtectionProxy() {
		delete realDocument;
	}

	void Read() override {
		realDocument->Read();
	}

	void Write(const std::string& content) override {
		if (accessLevel >= AccessLevel::READ_WRITE) {
			realDocument->Write(content);
		} else {
			std::cout << "Access denied: Insufficient permissions to write\n";
		}
	}

	void Delete() override {
		if (accessLevel == AccessLevel::ADMIN) {
			realDocument->Delete();
		} else {
			std::cout << "Access denied: Admin permissions required to delete\n";
		}
	}
};

// Smart Reference Proxy - reference counting
template<typename T>
class SmartPointer {
private:
	T* ptr;
	int* refCount;

	void Release() {
		if (refCount) {
			(*refCount)--;
			if (*refCount == 0) {
				delete ptr;
				delete refCount;
				std::cout << "Object deleted (ref count reached 0)\n";
			}
		}
	}

public:
	explicit SmartPointer(T* p = nullptr) : ptr(p), refCount(new int(1)) {
		std::cout << "SmartPointer created, ref count = 1\n";
	}

	SmartPointer(const SmartPointer& other) : ptr(other.ptr), refCount(other.refCount) {
		(*refCount)++;
		std::cout << "SmartPointer copied, ref count = " << *refCount << "\n";
	}

	~SmartPointer() {
		Release();
	}

	SmartPointer& operator=(const SmartPointer& other) {
		if (this != &other) {
			Release();
			ptr = other.ptr;
			refCount = other.refCount;
			(*refCount)++;
		}
		return *this;
	}

	T& operator*() const { return *ptr; }
	T* operator->() const { return ptr; }

	int GetRefCount() const { return *refCount; }
};

// Remote Proxy Example (simplified - no actual networking)
class RemoteService {
public:
	virtual ~RemoteService() = default;
	virtual std::string GetData(const std::string& key) = 0;
};

class RealRemoteService : public RemoteService {
public:
	std::string GetData(const std::string& key) override {
		// Simulate network delay
		std::this_thread::sleep_for(std::chrono::milliseconds(500));
		return "Data for key: " + key;
	}
};

class CachingProxy : public RemoteService {
private:
	RealRemoteService* realService;
	std::string cachedKey;
	std::string cachedValue;

public:
	CachingProxy() : realService(new RealRemoteService()) {}

	~CachingProxy() {
		delete realService;
	}

	std::string GetData(const std::string& key) override {
		if (key == cachedKey && !cachedValue.empty()) {
			std::cout << "Returning cached data\n";
			return cachedValue;
		}

		std::cout << "Fetching from remote service...\n";
		cachedKey = key;
		cachedValue = realService->GetData(key);
		return cachedValue;
	}
};

// Logging Proxy
class Service {
public:
	virtual ~Service() = default;
	virtual void Execute() = 0;
};

class RealService : public Service {
public:
	void Execute() override {
		std::cout << "Executing service\n";
	}
};

class LoggingProxy : public Service {
private:
	RealService* realService;

	void Log(const std::string& message) {
		auto now = std::chrono::system_clock::now();
		std::cout << "[LOG] " << message << "\n";
	}

public:
	LoggingProxy() : realService(new RealService()) {}

	~LoggingProxy() {
		delete realService;
	}

	void Execute() override {
		Log("Before execution");
		realService->Execute();
		Log("After execution");
	}
};

// Usage example
inline void ProxyPatternDemo() {
	std::cout << "=== Virtual Proxy Demo ===\n";
	// Proxy delays loading until needed
	Image* image1 = new ImageProxy("photo1.jpg");
	Image* image2 = new ImageProxy("photo2.jpg");

	std::cout << "\nNow displaying images:\n";
	image1->Display();  // Loads on first access
	image1->Display();  // Already loaded, no delay
	image2->Display();  // Loads on first access

	delete image1;
	delete image2;

	std::cout << "\n=== Protection Proxy Demo ===\n";
	Document* readOnlyDoc = new ProtectionProxy(new RealDocument(), AccessLevel::READ_ONLY);
	Document* readWriteDoc = new ProtectionProxy(new RealDocument(), AccessLevel::READ_WRITE);
	Document* adminDoc = new ProtectionProxy(new RealDocument(), AccessLevel::ADMIN);

	std::cout << "Read-only access:\n";
	readOnlyDoc->Write("Some content");  // Denied
	readOnlyDoc->Delete();               // Denied

	std::cout << "\nRead-write access:\n";
	readWriteDoc->Write("Some content"); // Allowed
	readWriteDoc->Delete();              // Denied

	std::cout << "\nAdmin access:\n";
	adminDoc->Write("Some content");     // Allowed
	adminDoc->Delete();                  // Allowed

	delete readOnlyDoc;
	delete readWriteDoc;
	delete adminDoc;

	std::cout << "\n=== Smart Reference Demo ===\n";
	{
		SmartPointer<RealImage> ptr1(new RealImage("photo3.jpg"));
		{
			SmartPointer<RealImage> ptr2 = ptr1;
			SmartPointer<RealImage> ptr3 = ptr1;
			std::cout << "Ref count: " << ptr1.GetRefCount() << "\n";
		}
		std::cout << "After inner scope, ref count: " << ptr1.GetRefCount() << "\n";
	}
	std::cout << "After outer scope\n";

	std::cout << "\n=== Caching Proxy Demo ===\n";
	RemoteService* service = new CachingProxy();
	service->GetData("key1");  // Fetch from remote
	service->GetData("key1");  // Return from cache
	service->GetData("key2");  // Fetch from remote

	delete service;

	std::cout << "\n=== Logging Proxy Demo ===\n";
	Service* loggedService = new LoggingProxy();
	loggedService->Execute();

	delete loggedService;
}

// Proxy vs Decorator:
// - Proxy: Controls access to object, often manages lifecycle
// - Decorator: Adds responsibilities to object
// - Proxy: Often creates/manages the real subject
// - Decorator: Wraps existing object provided by client

// Proxy vs Adapter:
// - Proxy: Same interface as real subject
// - Adapter: Converts one interface to another

// Benefits:
// 1. Controls access to real object
// 2. Can add additional behavior (logging, caching, lazy loading)
// 3. Real object can be in different address space (remote proxy)
// 4. Can optimize performance (virtual proxy, caching proxy)
// 5. Can add security (protection proxy)

// When to use Proxy:
// 1. Need lazy initialization (virtual proxy)
// 2. Need access control (protection proxy)
// 3. Need local representative for remote object (remote proxy)
// 4. Need smart reference with extra functionality
// 5. Need to add logging, caching, or other cross-cutting concerns

}  // namespace proxy_pattern