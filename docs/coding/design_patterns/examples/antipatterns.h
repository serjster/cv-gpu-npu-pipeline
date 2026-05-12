#pragma once
#include <iostream>
#include <map>
#include <memory>
#include <string>
#include <vector>

namespace anti_patterns {
// Anti-Patterns: Common solutions to recurring problems that are ineffective
// and counterproductive. These are patterns that should be avoided.

// ============================================================================
// 1. GOD OBJECT / GOD CLASS
// ============================================================================
// Problem: One class that does too much, knows too much, or controls too much
// Violates: Single Responsibility Principle

// BAD - God Object
class GodClass {
private:
	// Manages database
	std::string connectionString;

	// Manages UI
	void RenderUI() { /* ... */ }

	// Manages business logic
	void ProcessOrder() { /* ... */ }

	// Manages networking
	void SendHTTPRequest() { /* ... */ }

	// Manages file I/O
	void SaveToFile() { /* ... */ }

	// Manages logging
	void Log(const std::string &msg) { /* ... */ }

public:
	// Does everything!
	void DoEverything() {
		RenderUI();
		ProcessOrder();
		SendHTTPRequest();
		SaveToFile();
		Log("Did everything");
	}
};

// GOOD - Separated Responsibilities
class Database {
public:
	void Connect(const std::string &connStr) { /* ... */ }
};

class UIRenderer {
public:
	void Render() { /* ... */ }
};

class OrderProcessor {
public:
	void Process() { /* ... */ }
};

// ============================================================================
// 2. SPAGHETTI CODE
// ============================================================================
// Problem: Code with complex and tangled control flow

// BAD - Spaghetti Code
inline void ProcessDataBad(int type, int status, bool flag) {
	if (type == 1) {
		if (status == 0) {
			if (flag) {
				// do something
				for (int i = 0; i < 10; i++) {
					if (i % 2 == 0) {
						// more nesting
					} else {
						// even more logic
					}
				}
			} else {
				// different logic
			}
		} else if (status == 1) {
			// more branching
		}
	} else if (type == 2) {
		// completely different logic tree
	}
}

// GOOD - Clear structure with early returns and extraction
inline bool ShouldProcess(int type, int status, bool flag) { return type == 1 && status == 0 && flag; }

inline void ProcessEvenNumbers() { /* ... */ }
inline void ProcessOddNumbers() { /* ... */ }

inline void ProcessDataGood(int type, int status, bool flag) {
	if (!ShouldProcess(type, status, flag)) {
		return;
	}

	for (int i = 0; i < 10; i++) {
		if (i % 2 == 0) {
			ProcessEvenNumbers();
		} else {
			ProcessOddNumbers();
		}
	}
}

// ============================================================================
// 3. LAVA FLOW
// ============================================================================
// Problem: Dead code and forgotten design artifacts that nobody wants to touch

// BAD - Lava Flow
class LegacySystem {
private:
	// TODO: Remove this? (added in 2005)
	void OldMethod() { /* deprecated */ }

	// FIXME: This doesn't work anymore
	void BrokenMethod() { /* ... */ }

	// Not sure what this does, afraid to delete it
	void MysteryMethod() { /* ??? */ }

public:
	// The only method actually used
	void DoWork() {
		// Calls some of the above methods "just in case"
		OldMethod();
		// Main logic here
	}
};

// GOOD - Clean, documented code
class ModernSystem {
public:
	// Clear purpose, well-documented
	void DoWork() {
		// Only necessary logic
	}
};

// ============================================================================
// 4. GOLDEN HAMMER
// ============================================================================
// Problem: Using a familiar tool/pattern for every problem

// BAD - Using Singleton for everything
class ConfigSingleton {
public:
	static ConfigSingleton &GetInstance() {
		static ConfigSingleton instance;
		return instance;
	}
};

class LoggerSingleton {
public:
	static LoggerSingleton &GetInstance() {
		static LoggerSingleton instance;
		return instance;
	}
};

class DatabaseSingleton {
public:
	static DatabaseSingleton &GetInstance() {
		static DatabaseSingleton instance;
		return instance;
	}
};

// Even for things that should have multiple instances!
class UserSingleton { // BAD - Users should not be singleton!
public:
	static UserSingleton &GetInstance() {
		static UserSingleton instance;
		return instance;
	}
};

// GOOD - Use appropriate patterns for each situation
class Config {
	// Singleton is appropriate here
};

class Logger {
	// Could be singleton or dependency injection
};

class Database2 {
	// Consider connection pool instead of singleton
};

class User {
	// Regular class - should have multiple instances!
private:
	std::string name;
	int id;

public:
	User(const std::string &n, int i) : name(n), id(i) {}
};

// ============================================================================
// 5. CARGO CULT PROGRAMMING
// ============================================================================
// Problem: Using code/patterns without understanding why

// BAD - Cargo Cult
class CargoExample {
public:
	void DoSomething() {
		// Found this in a tutorial, not sure why it's needed
		try {
			int x = 5;
			// No exception possible here
		} catch (...) {
			// This will never execute
		}

		// Saw this in enterprise code, must be important
		for (int i = 0; i < 1; i++) {
			// Loop that runs once - why?
		}

		// Copy-pasted from Stack Overflow
		void *ptr = nullptr;
		if (ptr) { // Will always be false
			// Dead code
		}
	}
};

// GOOD - Understand what you write
class GoodExample {
public:
	void DoSomething() {
		int x = 5;
		// Clear, simple code that does what's needed
	}
};

// ============================================================================
// 6. POLTERGEIST / PROLIFERATION OF CLASSES
// ============================================================================
// Problem: Classes with limited responsibility and role, often just to invoke others

struct Foo {
	void DoWork() {}
};

// BAD - Poltergeist
class FooManager { // Does nothing useful
public:
	void ManageFoo(Foo *foo) {
		foo->DoWork(); // Just delegates
	}
};

class FooHelper { // Another useless middleman
public:
	void HelpFoo(Foo *foo) {
		FooManager manager;
		manager.ManageFoo(foo);
	}
};

// GOOD - Direct usage
inline void UseFoo() {
	Foo foo;
	foo.DoWork(); // Direct call, no unnecessary intermediaries
}

// ============================================================================
// 7. PREMATURE OPTIMIZATION
// ============================================================================
// Problem: Optimizing before knowing if it's needed

// BAD - Premature Optimization
class PrematureOptimization {
private:
	// Using bitwise operations for unclear performance gain
	int MultiplyBy16Bad(int x) {
		return x << 4; // Harder to read, compiler would optimize anyway
	}

	// Micro-optimizing loop structure
	void ProcessArrayBad(int *arr, int size) {
		// Unrolled loop "for performance"
		int i = 0;
		for (; i < size - 4; i += 4) {
			arr[i] *= 2;
			arr[i + 1] *= 2;
			arr[i + 2] *= 2;
			arr[i + 3] *= 2;
		}
		for (; i < size; i++) {
			arr[i] *= 2;
		}
	}

public:
	// GOOD - Clear, readable code
	int MultiplyBy16Good(int x) {
		return x * 16; // Clear intent, compiler optimizes
	}

	void ProcessArrayGood(int *arr, int size) {
		for (int i = 0; i < size; i++) {
			arr[i] *= 2; // Simple and clear
		}
	}
};

// ============================================================================
// 8. MAGIC NUMBERS / MAGIC STRINGS
// ============================================================================
// Problem: Unexplained literals in code

// BAD - Magic Numbers
inline void ProcessOrderBad(int status) {
	if (status == 42) { // What is 42?
		// Do something
	}

	constexpr int quantity = 10;
	double price = quantity * 1.07; // What is 1.07?
}

// GOOD - Named Constants
constexpr int ORDER_STATUS_COMPLETED = 42;
constexpr double TAX_RATE = 1.07;

inline void ProcessOrderGood(int status) {
	if (status == ORDER_STATUS_COMPLETED) {
		// Clear meaning
	}

	constexpr int quantity = 10;
	double price = quantity * TAX_RATE;
}

// ============================================================================
// 9. DEPENDENCY HELL / TIGHTLY COUPLED CODE
// ============================================================================
// Problem: Classes that are too interdependent

// Forward declaration for example
class SMTPServer {
public:
	void Connect(const std::string& host) { /* ... */ }
	void Send(const std::string& message) { /* ... */ }
};

// BAD - Tight Coupling
class EmailSenderBad {
public:
	void Send(const std::string &message) {
		// Hardcoded dependency
		SMTPServer server;
		server.Connect("smtp.example.com");
		server.Send(message);
	}
};

// GOOD - Loose Coupling with Dependency Injection
class IEmailService {
public:
	virtual ~IEmailService() = default;
	virtual void Send(const std::string &message) = 0;
};

class EmailSenderGood {
private:
	IEmailService *emailService;

public:
	explicit EmailSenderGood(IEmailService *service) : emailService(service) {}

	void Send(const std::string &message) { emailService->Send(message); }
};

// ============================================================================
// 10. BOAT ANCHOR
// ============================================================================
// Problem: Code retained "just in case" it's needed in the future

// BAD - Boat Anchor
class SystemWithAnchor {
private:
	// Kept "just in case we need to switch back"
	void OldImplementation() { /* not used */ }

	// "Might need this feature in the future"
	void FutureFeature() { /* never implemented */ }

	// "Don't delete, might be useful someday"
	void UnusedMethod() { /* ... */ }

public:
	void CurrentImplementation() {
		// Actually used code
	}
};

// GOOD - Clean code, use version control for history
class CleanSystem {
public:
	void CurrentImplementation() {
		// Only what's needed now
	}
};

// ============================================================================
// COMMON PITFALLS WITH DESIGN PATTERNS
// ============================================================================

// Forward declaration for examples
class GenericObject {
public:
	void DoSomething() { /* ... */ }
};

// 1. PATTERN OVERUSE - Using patterns when simple code would suffice
// BAD
class SimpleDataHolder {
	// Using complicated pattern for simple data storage
	static SimpleDataHolder &GetInstance() { /* ... */ }

private:
	std::map<std::string, std::string> data;
};

// GOOD - Just use a simple struct
struct DataHolder {
	std::string key;
	std::string value;
};

// 2. WRONG PATTERN - Using inappropriate pattern
// BAD - Using Factory for single object
class SingletonFactory {
public:
	static GenericObject *CreateObject() {
		return new GenericObject(); // Why use factory for single type?
	}
};

// GOOD - Direct instantiation
inline GenericObject *CreateObject() { return new GenericObject(); }

// Usage example
inline void AntiPatternsDemo() {
	std::cout << "=== Anti-Patterns Examples ===\n\n";

	std::cout << "1. God Object: One class doing too much\n";
	std::cout << "   FIX: Separate into specialized classes\n\n";

	std::cout << "2. Spaghetti Code: Complex nested logic\n";
	std::cout << "   FIX: Extract methods, use early returns\n\n";

	std::cout << "3. Lava Flow: Dead code nobody dares touch\n";
	std::cout << "   FIX: Clean up regularly, use version control\n\n";

	std::cout << "4. Golden Hammer: Using same pattern for everything\n";
	std::cout << "   FIX: Learn multiple patterns, use appropriate ones\n\n";

	std::cout << "5. Cargo Cult: Code without understanding\n";
	std::cout << "   FIX: Understand before using\n\n";

	std::cout << "6. Poltergeist: Useless intermediate classes\n";
	std::cout << "   FIX: Remove unnecessary indirection\n\n";

	std::cout << "7. Premature Optimization: Optimizing too early\n";
	std::cout << "   FIX: Profile first, optimize bottlenecks\n\n";

	std::cout << "8. Magic Numbers: Unexplained literals\n";
	std::cout << "   FIX: Use named constants\n\n";

	std::cout << "9. Tight Coupling: Too many dependencies\n";
	std::cout << "   FIX: Use interfaces and dependency injection\n\n";

	std::cout << "10. Boat Anchor: Code kept 'just in case'\n";
	std::cout << "    FIX: Delete unused code, trust version control\n";
}

// Key Lessons:
// 1. Simple is better than complex
// 2. Clear is better than clever
// 3. Don't use patterns just because they exist
// 4. Code should be maintainable and understandable
// 5. Follow SOLID principles
// 6. Refactor regularly
// 7. Write tests to enable safe changes
// 8. Use version control - don't be afraid to delete code
// 9. Profile before optimizing
// 10. Understand the problem before applying patterns
} // namespace anti_patterns
