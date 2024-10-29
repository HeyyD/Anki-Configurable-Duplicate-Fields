#!/usr/bin/env bash

ROOT_DIR=$(pwd)
TARGET_DIR=$ROOT_DIR/target
rm -rf $TARGET_DIR
mkdir -p $TARGET_DIR
TEMP_DIR=`mktemp -d`
echo Using temp dir $TEMP_DIR
cp __init__.py $TEMP_DIR
cp manifest.json $TEMP_DIR
mkdir $TEMP_DIR/configurable_duplicate_fields
cp configurable_duplicate_fields/__init__.py $TEMP_DIR/configurable_duplicate_fields
pushd $TEMP_DIR
zip -r configurable_duplicate_fields.zip .
echo Moving package to $TARGET_DIR
mv configurable_duplicate_fields.zip $TARGET_DIR
popd
rm -rf $TEMP_DIR
