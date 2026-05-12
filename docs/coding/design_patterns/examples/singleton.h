#pragma once
#include <iostream>
#include <mutex>
#include <memory>

namespace singleton_pattern {
// Singleton Pattern: Ensures a class has only one instance and provides a global
// point of access to it.

// Classic Singleton (not thread-safe)
class ClassicSingleton {
private:
	static ClassicSingleton* uniqueInstance;

	// Private constructor prevents instantiation
	ClassicSingleton() {}

public:
	// Delete copy constructor and assignment operator
	ClassicSingleton(const ClassicSingleton&) = delete;
	ClassicSingleton& operator=(const ClassicSingleton&) = delete;

	static ClassicSingleton* GetInstance() {
		if (uniqueInstance == nullptr) {
			uniqueInstance = new ClassicSingleton();
		}
		return uniqueInstance;
	}
};

// Initialize static member
ClassicSingleton* ClassicSingleton::uniqueInstance = nullptr;

// Thread-Safe Singleton with Double-Checked Locking
class ThreadSafeSingleton {
private:
	static ThreadSafeSingleton* uniqueInstance;
	static std::mutex mutex_;

	ThreadSafeSingleton() {}

public:
	ThreadSafeSingleton(const ThreadSafeSingleton&) = delete;
	ThreadSafeSingleton& operator=(const ThreadSafeSingleton&) = delete;

	static ThreadSafeSingleton* GetInstance() {
		if (uniqueInstance == nullptr) {
			std::lock_guard<std::mutex> lock(mutex_);
			if (uniqueInstance == nullptr) {
				uniqueInstance = new ThreadSafeSingleton();
			}
		}
		return uniqueInstance;
	}
};

// Initialize static members
ThreadSafeSingleton* ThreadSafeSingleton::uniqueInstance = nullptr;
std::mutex ThreadSafeSingleton::mutex_;

// Modern C++11 Thread-Safe Singleton (Meyer's Singleton)
// This is the recommended approach in modern C++
class ModernSingleton {
private:
	ModernSingleton() {
		std::cout << "Singleton instance created\n";
	}

public:
	ModernSingleton(const ModernSingleton&) = delete;
	ModernSingleton& operator=(const ModernSingleton&) = delete;

	static ModernSingleton& GetInstance() {
		// Thread-safe in C++11 and later
		static ModernSingleton instance;
		return instance;
	}

	void DoSomething() {
		std::cout << "Singleton doing something\n";
	}
};

// Practical Example: ChocolateBoiler
class ChocolateBoiler {
private:
	bool empty;
	bool boiled;

	ChocolateBoiler() : empty(true), boiled(false) {
		std::cout << "ChocolateBoiler created\n";
	}

public:
	ChocolateBoiler(const ChocolateBoiler&) = delete;
	ChocolateBoiler& operator=(const ChocolateBoiler&) = delete;

	static ChocolateBoiler& GetInstance() {
		static ChocolateBoiler instance;
		return instance;
	}

	void Fill() {
		if (IsEmpty()) {
			empty = false;
			boiled = false;
			std::cout << "Filling the boiler with milk/chocolate mixture\n";
		} else {
			std::cout << "Error: Boiler is already full\n";
		}
	}

	void Drain() {
		if (!IsEmpty() && IsBoiled()) {
			empty = true;
			std::cout << "Draining the boiled milk and chocolate\n";
		} else {
			std::cout << "Error: Cannot drain - boiler is empty or not boiled\n";
		}
	}

	void Boil() {
		if (!IsEmpty() && !IsBoiled()) {
			boiled = true;
			std::cout << "Bringing the contents to a boil\n";
		} else {
			std::cout << "Error: Cannot boil - boiler is empty or already boiled\n";
		}
	}

	bool IsEmpty() const { return empty; }
	bool IsBoiled() const { return boiled; }
};

// Anti-pattern: Global variable (what NOT to do)
// This is NOT a singleton and has many issues
class GlobalObject {
public:
	void DoSomething() {
		std::cout << "Global object doing something\n";
	}
};
// Don't do this:
// GlobalObject globalInstance;

// Usage example
inline void SingletonPatternDemo() {
	std::cout << "=== Modern Singleton Demo ===\n";
	ModernSingleton& singleton1 = ModernSingleton::GetInstance();
	ModernSingleton& singleton2 = ModernSingleton::GetInstance();

	std::cout << "Are they the same instance? "
			  << (&singleton1 == &singleton2 ? "Yes" : "No") << "\n\n";

	std::cout << "=== ChocolateBoiler Demo ===\n";
	ChocolateBoiler& boiler = ChocolateBoiler::GetInstance();
	boiler.Fill();
	boiler.Boil();
	boiler.Drain();
	boiler.Drain(); // This should fail
	boiler.Fill();
}

// Common Pitfalls:
// 1. Not thread-safe in classic implementation
// 2. Memory leak (never deleted) - consider using smart pointers
// 3. Testing difficulties - hard to mock
// 4. Hidden dependencies - violates Dependency Inversion Principle
// 5. Global state - makes code harder to reason about
// 6. Initialization order issues with static members

// When to use Singleton:
// - Logging
// - Configuration managers
// - Connection pools
// - Thread pools
// - Caches
// - Device drivers

// When NOT to use Singleton:
// - When you need multiple instances in tests
// - When the object has no shared state
// - When it makes testing difficult
// - As a replacement for global variables (that's an anti-pattern)
} // namespace singleton_pattern
