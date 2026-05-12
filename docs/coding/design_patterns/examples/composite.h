#pragma once
#include <iostream>
#include <vector>
#include <string>
#include <memory>

// Composite Pattern: Composes objects into tree structures to represent part-whole
// hierarchies. Composite lets clients treat individual objects and compositions
// of objects uniformly.

namespace composite_pattern {

// Component - interface for both leaf and composite objects
class MenuComponent {
public:
	virtual ~MenuComponent() = default;

	// Composite methods
	virtual void Add(MenuComponent* component) {
		throw std::runtime_error("Unsupported operation");
	}

	virtual void Remove(MenuComponent* component) {
		throw std::runtime_error("Unsupported operation");
	}

	virtual MenuComponent* GetChild(int i) {
		throw std::runtime_error("Unsupported operation");
	}

	// Operation methods
	virtual std::string GetName() const {
		throw std::runtime_error("Unsupported operation");
	}

	virtual std::string GetDescription() const {
		throw std::runtime_error("Unsupported operation");
	}

	virtual double GetPrice() const {
		throw std::runtime_error("Unsupported operation");
	}

	virtual bool IsVegetarian() const {
		throw std::runtime_error("Unsupported operation");
	}

	virtual void Print() const = 0;
};

// Leaf - MenuItem (no children)
class MenuItem : public MenuComponent {
private:
	std::string name;
	std::string description;
	bool vegetarian;
	double price;

public:
	MenuItem(const std::string& n, const std::string& desc, bool veg, double p)
		: name(n), description(desc), vegetarian(veg), price(p) {}

	std::string GetName() const override { return name; }
	std::string GetDescription() const override { return description; }
	double GetPrice() const override { return price; }
	bool IsVegetarian() const override { return vegetarian; }

	void Print() const override {
		std::cout << "  " << GetName();
		if (IsVegetarian()) {
			std::cout << "(v)";
		}
		std::cout << ", " << GetPrice() << "\n";
		std::cout << "     -- " << GetDescription() << "\n";
	}
};

// Composite - Menu (has children)
class Menu : public MenuComponent {
private:
	std::vector<MenuComponent*> menuComponents;
	std::string name;
	std::string description;

public:
	Menu(const std::string& n, const std::string& desc)
		: name(n), description(desc) {}

	~Menu() {
		for (auto* component : menuComponents) {
			delete component;
		}
	}

	void Add(MenuComponent* component) override {
		menuComponents.push_back(component);
	}

	void Remove(MenuComponent* component) override {
		auto it = std::find(menuComponents.begin(), menuComponents.end(), component);
		if (it != menuComponents.end()) {
			menuComponents.erase(it);
		}
	}

	MenuComponent* GetChild(int i) override {
		return menuComponents[i];
	}

	std::string GetName() const override { return name; }
	std::string GetDescription() const override { return description; }

	void Print() const override {
		std::cout << "\n" << GetName();
		std::cout << ", " << GetDescription() << "\n";
		std::cout << "---------------------\n";

		for (const auto* component : menuComponents) {
			component->Print();
		}
	}
};

// Waitress - client that uses composite structure
class Waitress {
private:
	MenuComponent* allMenus;

public:
	explicit Waitress(MenuComponent* menus) : allMenus(menus) {}

	void PrintMenu() const {
		allMenus->Print();
	}

	void PrintVegetarianMenu() const {
		PrintVegetarianMenu(allMenus);
	}

private:
	void PrintVegetarianMenu(const MenuComponent* component) const {
		try {
			// If it's a leaf (MenuItem), check if vegetarian
			if (component->IsVegetarian()) {
				component->Print();
			}
		} catch (const std::runtime_error&) {
			// If it's a composite (Menu), iterate through children
			// This is a bit awkward due to our design, but demonstrates the pattern
		}
	}
};

// Another example: File System
class FileSystemComponent {
public:
	virtual ~FileSystemComponent() = default;
	virtual void Display(int indent = 0) const = 0;
	virtual int GetSize() const = 0;

	virtual void Add(FileSystemComponent* component) {
		throw std::runtime_error("Unsupported operation");
	}

	virtual void Remove(FileSystemComponent* component) {
		throw std::runtime_error("Unsupported operation");
	}
};

// Leaf - File
class File : public FileSystemComponent {
private:
	std::string name;
	int size;

public:
	File(const std::string& n, int s) : name(n), size(s) {}

	void Display(int indent = 0) const override {
		std::cout << std::string(indent, ' ') << "- " << name
		          << " (" << size << " bytes)\n";
	}

	int GetSize() const override {
		return size;
	}
};

// Composite - Directory
class Directory : public FileSystemComponent {
private:
	std::string name;
	std::vector<FileSystemComponent*> children;

public:
	explicit Directory(const std::string& n) : name(n) {}

	~Directory() {
		for (auto* child : children) {
			delete child;
		}
	}

	void Add(FileSystemComponent* component) override {
		children.push_back(component);
	}

	void Remove(FileSystemComponent* component) override {
		auto it = std::find(children.begin(), children.end(), component);
		if (it != children.end()) {
			delete *it;
			children.erase(it);
		}
	}

	void Display(int indent = 0) const override {
		std::cout << std::string(indent, ' ') << "+ " << name << "/\n";
		for (const auto* child : children) {
			child->Display(indent + 2);
		}
	}

	int GetSize() const override {
		int totalSize = 0;
		for (const auto* child : children) {
			totalSize += child->GetSize();
		}
		return totalSize;
	}
};

// Modern C++ version using smart pointers
class ModernComponent {
public:
	virtual ~ModernComponent() = default;
	virtual void Display(int indent = 0) const = 0;
	virtual int GetSize() const = 0;
};

class ModernFile : public ModernComponent {
private:
	std::string name;
	int size;

public:
	ModernFile(const std::string& n, int s) : name(n), size(s) {}

	void Display(int indent = 0) const override {
		std::cout << std::string(indent, ' ') << "- " << name
		          << " (" << size << " bytes)\n";
	}

	int GetSize() const override { return size; }
};

class ModernDirectory : public ModernComponent {
private:
	std::string name;
	std::vector<std::unique_ptr<ModernComponent>> children;

public:
	explicit ModernDirectory(const std::string& n) : name(n) {}

	void Add(std::unique_ptr<ModernComponent> component) {
		children.push_back(std::move(component));
	}

	void Display(int indent = 0) const override {
		std::cout << std::string(indent, ' ') << "+ " << name << "/\n";
		for (const auto& child : children) {
			child->Display(indent + 2);
		}
	}

	int GetSize() const override {
		int totalSize = 0;
		for (const auto& child : children) {
			totalSize += child->GetSize();
		}
		return totalSize;
	}
};

// Usage example
inline void CompositePatternDemo() {
	std::cout << "=== Menu Composite Example ===\n";

	// Create menu structure
	MenuComponent* pancakeHouseMenu = new Menu("PANCAKE HOUSE MENU", "Breakfast");
	MenuComponent* dinerMenu = new Menu("DINER MENU", "Lunch");
	MenuComponent* cafeMenu = new Menu("CAFE MENU", "Dinner");
	MenuComponent* dessertMenu = new Menu("DESSERT MENU", "Dessert of course!");

	MenuComponent* allMenus = new Menu("ALL MENUS", "All menus combined");

	// Build the tree
	allMenus->Add(pancakeHouseMenu);
	allMenus->Add(dinerMenu);
	allMenus->Add(cafeMenu);

	// Add items to pancake house menu
	pancakeHouseMenu->Add(new MenuItem(
		"K&B's Pancake Breakfast",
		"Pancakes with scrambled eggs and toast",
		true,
		2.99
	));
	pancakeHouseMenu->Add(new MenuItem(
		"Regular Pancake Breakfast",
		"Pancakes with fried eggs, sausage",
		false,
		2.99
	));

	// Add items to diner menu
	dinerMenu->Add(new MenuItem(
		"Vegetarian BLT",
		"(Fakin') Bacon with lettuce & tomato on whole wheat",
		true,
		2.99
	));
	dinerMenu->Add(new MenuItem(
		"BLT",
		"Bacon with lettuce & tomato on whole wheat",
		false,
		2.99
	));
	dinerMenu->Add(new MenuItem(
		"Soup of the day",
		"Soup of the day, with a side of potato salad",
		false,
		3.29
	));
	dinerMenu->Add(new MenuItem(
		"Hotdog",
		"A hot dog, with sauerkraut, relish, onions, topped with cheese",
		false,
		3.05
	));

	// Add dessert menu as submenu of diner menu
	dinerMenu->Add(dessertMenu);

	dessertMenu->Add(new MenuItem(
		"Apple Pie",
		"Apple pie with a flakey crust, topped with vanilla ice cream",
		true,
		1.59
	));

	// Add items to cafe menu
	cafeMenu->Add(new MenuItem(
		"Veggie Burger and Air Fries",
		"Veggie burger on a whole wheat bun, lettuce, tomato, and fries",
		true,
		3.99
	));
	cafeMenu->Add(new MenuItem(
		"Soup of the day",
		"A cup of the soup of the day, with a side salad",
		false,
		3.69
	));

	// Print entire menu structure
	Waitress* waitress = new Waitress(allMenus);
	waitress->PrintMenu();

	delete waitress;
	delete allMenus; // This will recursively delete all children

	std::cout << "\n=== File System Composite Example ===\n";

	// Create file system structure
	Directory* root = new Directory("root");
	Directory* home = new Directory("home");
	Directory* user = new Directory("user");

	File* bashrc = new File(".bashrc", 1024);
	File* profile = new File(".profile", 2048);

	Directory* documents = new Directory("documents");
	File* resume = new File("resume.pdf", 50000);
	File* coverletter = new File("coverletter.pdf", 30000);

	// Build tree
	root->Add(home);
	home->Add(user);
	user->Add(bashrc);
	user->Add(profile);
	user->Add(documents);
	documents->Add(resume);
	documents->Add(coverletter);

	// Display structure
	root->Display();
	std::cout << "Total size: " << root->GetSize() << " bytes\n";

	delete root; // Recursively deletes all children

	std::cout << "\n=== Modern C++ with Smart Pointers ===\n";

	auto modernRoot = std::make_unique<ModernDirectory>("root");
	auto modernHome = std::make_unique<ModernDirectory>("home");
	auto modernDocs = std::make_unique<ModernDirectory>("documents");

	modernDocs->Add(std::make_unique<ModernFile>("file1.txt", 100));
	modernDocs->Add(std::make_unique<ModernFile>("file2.txt", 200));

	modernHome->Add(std::move(modernDocs));
	modernRoot->Add(std::move(modernHome));

	modernRoot->Display();
	std::cout << "Total size: " << modernRoot->GetSize() << " bytes\n";
}

// Benefits of Composite Pattern:
// 1. Treats individual objects and compositions uniformly
// 2. Makes client code simple - doesn't need to know if dealing with leaf or composite
// 3. Easy to add new kinds of components
// 4. Can create complex tree structures

// Tradeoffs:
// 1. Can make design overly general
// 2. Hard to restrict components of composite (type safety)
// 3. Methods in Component interface may not make sense for all subclasses

// Design Principle: Single Responsibility vs Transparency
// Composite pattern trades Single Responsibility Principle for transparency
// - Component has both composite and leaf operations
// - This allows client to treat composites and leaves uniformly
// - But it means Component has multiple responsibilities

// When to use Composite:
// 1. Represent part-whole hierarchies
// 2. Want clients to ignore difference between compositions and individual objects
// 3. Tree structures (file systems, GUI components, organizational charts, etc.)

} // namespace CompositePattern
