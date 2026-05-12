#pragma once
#include <iostream>
#include <ostream>

using namespace std;

namespace strategy_pattern {

struct FlyBehavior {
	virtual ~FlyBehavior() = default;
	virtual void Fly() = 0;
};

struct FlyWithWings : FlyBehavior {
	void Fly() override { std::cout << "I'm flying!!!" << endl; }
};

struct FlyNoWay : FlyBehavior {
	void Fly() override { std::cout << "I can't fly!!!" << endl; }
};

struct FlyRockerPowered : FlyBehavior {
	void Fly() override { std::cout << "I'm flying with a rocker!!!" << endl; }
};

struct QuackBehavior {
	virtual ~QuackBehavior() = default;
	virtual void Quack() = 0;
};

struct QuackImpl : QuackBehavior {
	void Quack() override { std::cout << "Quack!!!" << endl; }
};

struct MuteQuack : QuackBehavior {
	void Quack() override { std::cout << "Silence!!!" << endl; }
};

struct Squeak : QuackBehavior {
	void Quack() override { std::cout << "Squeak!!!" << endl; }
};

struct Duck {
	std::string name_;
	unique_ptr<FlyBehavior> flyBehaviour_;
	unique_ptr<QuackBehavior> quackBehaviour_;

	Duck(std::string name, unique_ptr<FlyBehavior> flyBehaviour, unique_ptr<QuackBehavior> quackBehaviour) :
		name_(std::move(name)), flyBehaviour_(std::move(flyBehaviour)), quackBehaviour_(std::move(quackBehaviour)) {
		assert(flyBehaviour_ != nullptr);
		assert(quackBehaviour_ != nullptr);
	}

	virtual ~Duck() {}

	void PerformFly() const {
		assert(flyBehaviour_ != nullptr);
		flyBehaviour_->Fly();
	}

	void PerformQuack() const {
		assert(quackBehaviour_ != nullptr);
		quackBehaviour_->Quack();
	}

	void SetFlyBehavior(unique_ptr<FlyBehavior> fb) {
		flyBehaviour_ = std::move(fb);
	}

	void SetQuackBehavior(unique_ptr<QuackBehavior> qb) {
		quackBehaviour_ = std::move(qb);
	}

	virtual void Display() {
		cout << endl;
		cout << "I'm a " << name_ << "!" << endl;
		PerformFly();
		PerformQuack();
		cout << endl;
	}
};

struct ModelDuck : Duck {
	ModelDuck() : Duck("Model Duck"s, make_unique<FlyWithWings>(), make_unique<QuackImpl>()) {}
};

struct MallardDuck : Duck {
	MallardDuck() : Duck("MallardDuck"s, make_unique<FlyWithWings>(), make_unique<QuackImpl>()) {}
};

struct RubberDucky : Duck {
	RubberDucky() : Duck("RubberDucky"s, make_unique<FlyNoWay>(), make_unique<Squeak>()) {}
};

} // namespace strategy_pattern
