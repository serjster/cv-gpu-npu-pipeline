#pragma once
#include <iostream>
#include <string>

namespace template_method_pattern {
// Template Method Pattern: Defines the skeleton of an algorithm in a method,
// deferring some steps to subclasses. Template Method lets subclasses redefine
// certain steps of an algorithm without changing the algorithm's structure.

// Abstract class with template method
class CaffeineBeverage {
public:
	virtual ~CaffeineBeverage() = default;

	// Template method - defines algorithm skeleton
	// Final to prevent overriding the template
	void PrepareRecipe() {
		BoilWater();
		Brew();
		PourInCup();
		if (CustomerWantsCondiments()) {  // Hook method
			AddCondiments();
		}
	}

protected:
	// Primitive operations - must be implemented by subclasses
	virtual void Brew() = 0;
	virtual void AddCondiments() = 0;

	// Concrete operations - same for all subclasses
	void BoilWater() {
		std::cout << "Boiling water\n";
	}

	void PourInCup() {
		std::cout << "Pouring into cup\n";
	}

	// Hook method - subclasses can override but don't have to
	virtual bool CustomerWantsCondiments() {
		return true;
	}
};

// Concrete class - Coffee
class Coffee : public CaffeineBeverage {
protected:
	void Brew() override {
		std::cout << "Dripping Coffee through filter\n";
	}

	void AddCondiments() override {
		std::cout << "Adding Sugar and Milk\n";
	}

	bool CustomerWantsCondiments() override {
		std::string answer = GetUserInput();
		return answer == "y" || answer == "Y";
	}

private:
	std::string GetUserInput() {
		// In real implementation, would get user input
		// For demo, just return "y"
		return "y";
	}
};

// Concrete class - Tea
class Tea : public CaffeineBeverage {
protected:
	void Brew() override {
		std::cout << "Steeping the tea\n";
	}

	void AddCondiments() override {
		std::cout << "Adding Lemon\n";
	}
};

// Tea without condiments (using hook)
class TeaWithHook : public CaffeineBeverage {
protected:
	void Brew() override {
		std::cout << "Steeping the tea\n";
	}

	void AddCondiments() override {
		std::cout << "Adding Lemon\n";
	}

	bool CustomerWantsCondiments() override {
		return false;  // Skip condiments
	}
};

// Another example: Game template
class Game {
public:
	virtual ~Game() = default;

	// Template method
	void Play() {
		Initialize();
		StartPlay();
		while (!IsFinished()) {
			MakeMove();
		}
		EndPlay();
	}

protected:
	virtual void Initialize() = 0;
	virtual void StartPlay() = 0;
	virtual void MakeMove() = 0;
	virtual bool IsFinished() = 0;
	virtual void EndPlay() = 0;
};

class Chess : public Game {
private:
	int moveCount = 0;

protected:
	void Initialize() override {
		std::cout << "Chess Game Initialized! Start playing.\n";
		moveCount = 0;
	}

	void StartPlay() override {
		std::cout << "Game Started. First Player is white side.\n";
	}

	void MakeMove() override {
		moveCount++;
		std::cout << "Move " << moveCount << " completed\n";
	}

	bool IsFinished() override {
		return moveCount >= 3;  // End after 3 moves for demo
	}

	void EndPlay() override {
		std::cout << "Game Finished!\n";
	}
};

class Football : public Game {
private:
	int quarter = 0;

protected:
	void Initialize() override {
		std::cout << "Football Game Initialized! Start playing.\n";
		quarter = 0;
	}

	void StartPlay() override {
		std::cout << "Game Started. Kick off!\n";
	}

	void MakeMove() override {
		quarter++;
		std::cout << "Quarter " << quarter << " completed\n";
	}

	bool IsFinished() override {
		return quarter >= 4;
	}

	void EndPlay() override {
		std::cout << "Game Finished!\n";
	}
};

// Real-world example: Data processor
class DataProcessor {
public:
	virtual ~DataProcessor() = default;

	// Template method
	void Process() {
		OpenFile();
		ReadData();
		if (IsValid()) {
			ProcessData();
			if (ShouldSaveResults()) {
				SaveResults();
			}
		}
		CloseFile();
	}

protected:
	// Abstract methods
	virtual void ReadData() = 0;
	virtual void ProcessData() = 0;

	// Concrete methods
	void OpenFile() {
		std::cout << "Opening file...\n";
	}

	void CloseFile() {
		std::cout << "Closing file...\n";
	}

	void SaveResults() {
		std::cout << "Saving results...\n";
	}

	// Hook methods
	virtual bool IsValid() {
		return true;
	}

	virtual bool ShouldSaveResults() {
		return true;
	}
};

class CSVProcessor : public DataProcessor {
protected:
	void ReadData() override {
		std::cout << "Reading CSV data...\n";
	}

	void ProcessData() override {
		std::cout << "Processing CSV data...\n";
	}
};

class JSONProcessor : public DataProcessor {
protected:
	void ReadData() override {
		std::cout << "Reading JSON data...\n";
	}

	void ProcessData() override {
		std::cout << "Processing JSON data...\n";
	}

	bool ShouldSaveResults() override {
		return false;  // Don't save JSON results
	}
};

// Usage example
inline void TemplateMethodPatternDemo() {
	std::cout << "=== Making Tea ===\n";
	Tea* tea = new Tea();
	tea->PrepareRecipe();

	std::cout << "\n=== Making Coffee ===\n";
	Coffee* coffee = new Coffee();
	coffee->PrepareRecipe();

	std::cout << "\n=== Making Tea Without Condiments ===\n";
	TeaWithHook* teaNoLemon = new TeaWithHook();
	teaNoLemon->PrepareRecipe();

	std::cout << "\n=== Playing Chess ===\n";
	Game* chess = new Chess();
	chess->Play();

	std::cout << "\n=== Playing Football ===\n";
	Game* football = new Football();
	football->Play();

	std::cout << "\n=== Processing CSV ===\n";
	DataProcessor* csvProcessor = new CSVProcessor();
	csvProcessor->Process();

	std::cout << "\n=== Processing JSON ===\n";
	DataProcessor* jsonProcessor = new JSONProcessor();
	jsonProcessor->Process();

	delete tea;
	delete coffee;
	delete teaNoLemon;
	delete chess;
	delete football;
	delete csvProcessor;
	delete jsonProcessor;
}

// Key concepts:
// 1. Abstract class defines template method with algorithm skeleton
// 2. Primitive operations (abstract) - must be overridden
// 3. Concrete operations - common to all subclasses
// 4. Hook methods - optional override points with default behavior
// 5. Template method should be final to prevent override

// Hollywood Principle: "Don't call us, we'll call you"
// High-level components call low-level components, not the other way around
// Prevents "dependency rot" where high and low level components depend on each other

// When to use Template Method:
// 1. Multiple classes have similar algorithms with slight variations
// 2. Want to control which parts of algorithm can be customized
// 3. Want to avoid code duplication
// 4. Want to implement the invariant parts once and let subclasses implement varying behavior

// Template Method vs Strategy:
// - Template Method: Uses inheritance, compile-time algorithm selection
// - Strategy: Uses composition, runtime algorithm selection
// - Template Method: Defines algorithm structure in base class
// - Strategy: Encapsulates entire algorithm as separate object
} // namespace template_method_pattern